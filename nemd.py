#!/usr/bin/env python
#-*- coding: utf-8 -*-

import ghost as gh
import logging

log_handler = logging.FileHandler('debug.log')

ghost = gh.Ghost(log_handler=log_handler,log_level=logging.WARNING)
logging.info('Start Logging')

import urllib, urllib2, json, os, sys, codecs
import time, argparse


user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.95 Safari/537.36'
session = None
api_pre = "http://music.163.com/weapi/%s"

api_url = "song/enhance/player/url"
api_detail = "song/detail"
api_album = api_pre%"album/"

web_pre = 'http://music.163.com/%s'
web_song = web_pre%'#/song?id='


web_album = web_pre%"#/album?id="
#songs_playlist = 


outchain_pre = "http://music.163.com/outchain/player?%s"
outchain = outchain_pre%"type=2&id="
outchain_auto = outchain_pre%"type=2&auto=1&id="
outchain_album = outchain_pre%"type=1&id="



def new_session():
	return ghost.start(download_images=False,user_agent=user_agent,plugins_enabled=False)



# version 2
def pick_rsc(ex, cri):
	ret = []
	for item in ex:
		if cri(item.url, item.content):
			ret.append(item)
			print item.url
	return ret


def check_dir(prefix):
	if len(prefix)==0:
		return true
	if not os.path.exists(prefix):
		os.makedirs(prefix)
		print 'make directory',prefix
	return os.path.isdir(prefix)	


def check_ex(ex,info=None):
	if ex is None or len(ex) == 0:
			raise Exception("No valid response", info)



	


class Song():
	def __init__(self, detail):
		self.id = detail['id']
		self.name = detail['name']
		self.artists = detail['artists'] if 'artists' in detail else detail['ar']
		self.album = detail['album'] if 'album' in detail else detail['al']
		self.url = detail['mp3Url'] if 'mp3Url' in detail else ''



def check_loaded(ex, cri):
	if ex is None or len(ex) == 0:
		return False
	for item in ex:
		if cri(item.url):
			return True
	return False			


def wait_for_rsc(s, cri, cri_extra=lambda url:True, timeout=5):
	time1 = time.time()
	ex = [];
	
	while time.time()-time1<timeout:
		s.sleep(.5)
		if len(s.http_resources)==0:
			continue
		ex += s._release_last_resources()
		print 'wait len', len(ex)
		if check_loaded(ex, cri) and check_loaded(ex, cri_extra):
			#print 'loaded'
			return ex				
	return ex			


def get_info_from_websong(song_id):
	song_url = None
	song_detail = None
	page = None
	ex = None

	try:
		session.open(web_song + str(song_id))
	except Exception,e:
		print e

	try:
		session.wait_for_selector('#g_iframe')
		#print 'got iframe'
		session.frame('contentFrame')
		session.wait_for_selector('a[data-res-action="play"]')
		#print 'got play button'
	except Exception,e:
		print e	

	session.click('a[data-res-action="play"]', expect_loading=False)
	# another implementation of wait_for
	ex = wait_for_rsc(session, lambda url:url.find(api_url)>=0, lambda url:url.find(api_detail)>=0)
	print 'wait rsc len', len(ex)
	check_ex(ex, song_id)
	session.frame() #return to the mainframe
		
	for item in ex:
		if item.url.find(api_url)>=0:
			song_url = str(item.content)
		elif item.url.find(api_detail)>=0:
			song_detail = str(item.content)		

	if song_url is None or song_detail is None:
		#TODO: wait_for_resource_loaded
		raise Exception("No valid response", song_id)		

	song_url = json.loads(song_url)['data'][0]
	song_detail = json.loads(song_detail)['songs'][0]
	#print song_detail
	return song_url, Song(song_detail)



# the url is pernament, may fail for copyright restriction
def get_info_from_outchain(song_id):
	song_detail = None
	page = None
	ex = None
	try:
		page,ex = session.open(outchain + str(song_id))
	except Exception,e:
		print e
		ex = session.http_resources
	finally:
		check_ex(ex, song_id)
		for item in ex:
			if item.url.find(api_detail)>=0:
				song_detail = str(item.content)
			
	if song_detail is None:
		raise Exception("No valid response", song_id)

	return 	Song(json.loads(song_detail)['songs'][0])



# outchain autoplay, the url is for CDN
def get_info_from_outchain_auto(song_id):
	song_url = None
	song_detail = None
	page = None
	ex = None

	try:
		page,ex = session.open(outchain_auto + str(song_id))
	except Exception,e:
		print e
		ex = session.http_resources
	finally:
		check_ex(ex, song_id)
		for item in ex:
			if item.url.find(api_url)>=0:
				song_url = str(item.content)
			elif item.url.find(api_detail)>=0:
				song_detail = str(item.content)
	if song_url is None or song_detail is None:
		raise Exception("No valid response", song_id)

	song_url = 	json.loads(song_url)['data'][0]
	song_detail = json.loads(song_detail)['songs'][0]

	return song_url, Song(song_detail)	



def get_info_smart(song_id):
	url = None
	detail = None
	try:
		detail = get_info_from_outchain(song_id)
		url = detail.url
	except Exception, e:
		print e




get_info_methods = {
	'web': get_info_from_websong,
	'outchain': get_info_from_outchain,
	'outchain_auto': get_info_from_outchain_auto
}


def get_album(album_id):
	ex = None
	session.open(outchain_album+str(album_id),wait=False)
	ex = wait_for_rsc(session, lambda url:url.find(api_album)>=0)
	check_ex(ex, album_id)
	
	songs = []
	for item in ex:
		print item.url
		if item.url.find(api_album)>=0:
			print item.headers
			songs.append(item)

	#songs = pick_rsc(ex, lambda url,content:url.find(api_album)>=0)
	if len(songs)>0:
		songs = json.loads(str(songs[0].content))
		songs = songs['album']['songs']
	else:
		raise Exception('No song list fetched!')	

	return songs	




def test_cdn(song_id, logfile,prefix='download'):
	
	url, detail = get_info_from_outchain_auto(song_id)
	filename = "%s-%s.mp3"%(detail.artists[0]['name'], detail.name)
	url = url['url']


	cdn_file = open('./cdn.txt', 'rb')
	CDN_list = cdn_file.read().split('\n')
	cdn_file.close()
	print CDN_list

	
	if not check_dir(prefix):
		raise Exception('not directory', prefix)
	
	logfile.writelines('%d,%s,%s,%s\n'%(song_id, detail.artists[0]['name'], detail.name, url))
	for cdn in CDN_list:

		try:
			urllib.urlretrieve(url.replace('http:/', 'http://'+cdn), os.path.join(prefix, cdn + filename))
			logfile.writelines('download %s\n'%cdn)
		except Exception,e:
			print e
			logfile.writelines('error %s\n'%cdn)
		finally:
			print 'processed %s'%cdn		




def test_web(song_id,logfile,prefix='download'):
	

	url, detail = get_info_from_websong(song_id) #get_info_from_outchain(song_id)
	artist = detail.artists[0]['name'] if len(detail.artists)>0 else 'Unknown'
	if len(detail.artists) > 1:
		#TODO: add somgthing
		pass
	filename = "%s-%s.mp3"%(artist, detail.name)
	url = url['url']


	if not check_dir(prefix):
		raise Exception('not directory', prefix)

	logfile.writelines('%d,%s,%s,%s\n'%(song_id, artist, detail.name, url))

	try:
		urllib.urlretrieve(url, os.path.join(prefix, filename))
		logfile.writelines('success\n')
	except Exception,e:
		print e
		logfile.writelines('failure\n')


def test_album(album_id,logfile,prefix='download'):
	
	songs = get_album(album_id)
	song_list = [song['id'] for song in songs]
	print song_list

	for id in song_list:
		time1 = time.time()
		try:
			test_web(id,logfile,prefix)
			print 'succeed'
			
		except Exception,e:
			print e
			print 'fail'
		time2 = time.time()
		print 'time ellapse: ', time2 - time1


def apply_proxy(host, port):
	host = str(host)
	port = int(port)
	try:	
		session.set_proxy('https', host=host, port=port)
	except Exception,e:
		print 'no_proxy', e	

	session.wait_timeout = 20	




# step 1: obtain url

if __name__ == "__main__":
	import 	argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('type',type=str,help="download music by song_id or album_id",choices=['album','song'])
	parser.add_argument('id',type=int,help="song_id or album_id")
	parser.add_argument('--outchain',action='store_true')
	parser.add_argument('-p','--prefix',type=str,help="path to save music",default='download')
	parser.add_argument('-l','--log',type=str,help="log filename",default='nemd.log')
	args = parser.parse_args()


	album_id = 3367211
	song_id = 35804599 # 451113440 #

	logfile = codecs.open(args.log, 'wb', 'utf-8')

	session = new_session()

	#apply_proxy('112.114.173.88', 8998)

	try:
		#print get_info_from_outchain(451113440).url
		#print get_info_from_outchain(35804599).url
		if args.type == 'album':
			test_album(args.id, logfile, args.prefix)
		elif args.type == 'song':
			test_web(args.id, logfile, args.prefix)	
		else:
			test_cdn(args.id, logfile, args.prefix)	
		#pass
	except Exception,e:
		print e
	finally:
		logfile.close()
		session.exit()

	print 'finished'

	

