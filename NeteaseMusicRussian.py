# -*- coding: utf-8 -*-
'''
脚本基于https://github.com/darknessomi/musicbox/blob/master/NEMbox/api.py实现
'''

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import


import os
import json
import hashlib
import random
import base64
import binascii

from Crypto.Cipher import AES

from pymongo import MongoClient
from pymongo import errors

import requests


client = MongoClient('localhost', 27017)
db_playlists = client.netease['playlists']
db_songs = client.netease['songs']

#空格已包含,无需判断单词间的空格
Rus_Chars = u'АБВГДЕЁЖЗИЙКЛМН'\
            u"ОПРСТУФХЦЧШЩЪЫЬЭЮЯ"\
            u'абвгдеёжзийклмнопрстуфхцчшщъыьэюя1234567890 '


default_timeout = 10


modulus = ('00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7'
           'b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280'
           '104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932'
           '575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b'
           '3ece0462db0a22b8e7')

nonce = '0CoJUm6Qyw8W8jud'
pubKey = '010001'


#判断是否为俄语歌曲
def is_RUS(name):
    Rus_count = 0
    nonRus_count = 0
    for i in name:
        if i in Rus_Chars:
            Rus_count += 1
        else:
            nonRus_count += 1
    if Rus_count and nonRus_count == 0: return True
    return False


# 歌曲加密算法, 基于https://github.com/yanunon/NeteaseCloudMusic脚本实现
def encrypted_id(id):
    magic = bytearray('3go8&$8*3*3h0k(2)2', 'u8')
    song_id = bytearray(id, 'u8')
    magic_len = len(magic)
    for i, sid in enumerate(song_id):
        song_id[i] = sid ^ magic[i % magic_len]
    m = hashlib.md5(song_id)
    result = m.digest()
    result = base64.b64encode(result)
    result = result.replace(b'/', b'_')
    result = result.replace(b'+', b'-')
    return result.decode('u8')


# 登录加密算法, 基于https://github.com/stkevintan/nw_musicbox脚本实现
def encrypted_request(text):
    text = json.dumps(text)
    secKey = createSecretKey(16)
    encText = aesEncrypt(aesEncrypt(text, nonce), secKey)
    encSecKey = rsaEncrypt(secKey, pubKey, modulus)
    data = {'params': encText, 'encSecKey': encSecKey}
    return data


def aesEncrypt(text, secKey):
    pad = 16 - len(text) % 16
    text = text + chr(pad) * pad
    encryptor = AES.new(secKey, 2, '0102030405060708')
    ciphertext = encryptor.encrypt(text)
    ciphertext = base64.b64encode(ciphertext).decode('u8')
    return ciphertext


def rsaEncrypt(text, pubKey, modulus):
    text = text[::-1]
    rs = pow(int(binascii.hexlify(text), 16), int(pubKey, 16)) % int(modulus, 16)
    return format(rs, 'x').zfill(256)


def createSecretKey(size):
    return binascii.hexlify(os.urandom(size))[:16]


# list去重
def uniq(arr):
    arr2 = list(set(arr))
    arr2.sort(key=arr.index)
    return arr2

# 获取高音质mp3 url
def geturl(song):
    music = song['lMusic']
    quality = 'LD'
    quality = quality + ' {0}k'.format(music['bitrate'] // 1000)
    song_id = str(music['dfsId'])
    enc_id = encrypted_id(song_id)
    url = 'http://m%s.music.126.net/%s/%s.mp3' % (random.randrange(1, 3),
                                                  enc_id, song_id)
    return url, quality

class NetEase(object):

    def __init__(self):
        self.header = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,gl;q=0.6,zh-TW;q=0.4',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': 'music.163.com',
            'Referer': 'http://music.163.com/search/',
            'User-Agent':
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/33.0.1750.152 Safari/537.36'  # NOQA
        }
        self.cookies = {'appver': '1.5.2'}
        self.playlist_class_dict = {}
        self.session = requests.Session()



    def httpRequest(self,
                    method,
                    action,
                    query=None,
                    urlencoded=None,
                    callback=None,
                    timeout=None):
        connection = json.loads(self.rawHttpRequest(
            method, action, query, urlencoded, callback, timeout))
        return connection

    def rawHttpRequest(self,
                       method,
                       action,
                       query=None,
                       urlencoded=None,
                       callback=None,
                       timeout=None):
        if method == 'GET':
            url = action if query is None else action + '?' + query
            connection = self.session.get(url,
                                          headers=self.header,
                                          timeout=default_timeout)

        elif method == 'POST':
            connection = self.session.post(action,
                                           data=query,
                                           headers=self.header,
                                           timeout=default_timeout)

        elif method == 'Login_POST':
            connection = self.session.post(action,
                                           data=query,
                                           headers=self.header,
                                           timeout=default_timeout)
        connection.encoding = 'UTF-8'

        return connection.text

    # 歌单（网友精选碟） hot||new http://music.163.com/#/discover/playlist/
    def top_playlists(self, category=u'小语种', order='hot', offset=0, limit=10):
        action = 'http://music.163.com/api/playlist/list?cat={}&order={}&offset={}&total={}&limit={}'.format(  # NOQA
            category, order, offset, 'true' if offset else 'false',
            limit)  # NOQA
        try:
            data = self.httpRequest('GET', action)
            return data['playlists']
        except requests.exceptions.RequestException as e:
            print(e)
            return []

    # 歌单详情
    def playlist_detail(self, playlist_id):
        action = 'http://music.163.com/api/playlist/detail?id={}'.format(
            playlist_id)
        try:
            data = self.httpRequest('GET', action)
            return data['result']['tracks']
        except requests.exceptions.RequestException as e:
            print(e)
            return []

    def song_comments(self, music_id, offset=0, total='fasle', limit=1):
        action = 'http://music.163.com/api/v1/resource/comments/R_SO_4_{}/?rid=R_SO_4_{}&\
            offset={}&total={}&limit={}'.format(music_id, music_id, offset, total, limit)
        try:
            comments = self.httpRequest('GET', action)
            return comments
        except requests.exceptions.RequestException as e:
            print(e)
            return []


    # lyric http://music.163.com/api/song/lyric?os=osx&id= &lv=-1&kv=-1&tv=-1
    def song_lyric(self, music_id):
        action = 'http://music.163.com/api/song/lyric?os=osx&id={}&lv=-1&kv=-1&tv=-1'.format(  # NOQA
            music_id)
        try:
            data = self.httpRequest('GET', action)
            if 'lrc' in data and data['lrc']['lyric'] is not None:
                lyric_info = data['lrc']['lyric']
            else:
                lyric_info = '未找到歌词'
            return lyric_info
        except requests.exceptions.RequestException as e:
            print(e)
            return []

    def song_tlyric(self, music_id):
        action = 'http://music.163.com/api/song/lyric?os=osx&id={}&lv=-1&kv=-1&tv=-1'.format(  # NOQA
            music_id)
        try:
            data = self.httpRequest('GET', action)
            if 'tlyric' in data and data['tlyric'].get('lyric') is not None:
                lyric_info = data['tlyric']['lyric'][1:]
            else:
                lyric_info = '未找到歌词翻译'
            return lyric_info
        except requests.exceptions.RequestException as e:
            print(e)
            return []


    def dig_info(self, data, dig_type):
        if dig_type == 'songs' or dig_type == 'fmsongs':
            for i in range(0, len(data)):
                if not is_RUS(data[i]['name']):
                    continue
                url, quality = geturl(data[i])

                if data[i]['album'] is not None:
                    album_name = data[i]['album']['name']
                    album_id = data[i]['album']['id']
                else:
                    album_name = '未知专辑'
                    album_id = ''

                song_info = {
                    '_id': data[i]['id'],
                    'artist': [],
                    'song_name': data[i]['name'],
                    'album_name': album_name,
                    'album_id': album_id,
                    'mp3_url': url,
                    'quality': quality
                }
                song_info['url'] = "http://music.163.com/#/song?id={}".format(song_info['_id'])
                song_info['lyric'] = self.song_lyric(song_info['_id'])
                song_info['tlyric'] = self.song_tlyric(song_info['_id'])
                song_info['commentCount'] = self.song_comments(song_info['_id'])['total']
                if 'artist' in data[i]:
                    song_info['artist'] = data[i]['artist']
                elif 'artists' in data[i]:
                    for j in range(0, len(data[i]['artists'])):
                        song_info['artist'].append(data[i]['artists'][j][
                            'name'])
                    song_info['artist'] = ', '.join(song_info['artist'])
                else:
                    song_info['artist'] = '未知艺术家'
                try:
                    db_songs.insert(song_info)
                except errors.DuplicateKeyError:
                    print('Song _id DuplicateKEYError')
                    pass

    def get_russian(self):
        '''
        小语种热门约1470张歌单
        '''
        # self.login(user, passwd)
        for offset in xrange(0, 1500, 50):
            playlists = self.top_playlists(category=u'小语种', order='hot', offset=offset, limit=50)
            for playlist in playlists:
                insert_playlist = {}
                insert_playlist['_id'] = playlist['id']
                insert_playlist['trackCount'] = playlist['trackCount']
                insert_playlist['commentCount'] = playlist['commentCount']
                insert_playlist['description'] = playlist['description']
                insert_playlist['shareCount'] = playlist['shareCount']
                insert_playlist['subscribedCount'] = playlist['subscribedCount']
                insert_playlist['playCount'] = playlist['playCount']
                try:
                    detail = self.playlist_detail(insert_playlist['_id'])
                except:
                    print("http://music.163.com/#/playlist?id={}".format(insert_playlist['_id']))
                    detail = []
                print(insert_playlist['_id'])
                print('Page:{}'.format(int((offset/50)+1)))
                try:
                    db_playlists.insert(insert_playlist)
                except errors.DuplicateKeyError:
                    print('Playlist _id DuplicateKEYError')
                self.dig_info(detail, 'songs')


if __name__ == '__main__':
    ne = NetEase()
    ne.get_russian()
