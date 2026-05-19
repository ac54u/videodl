'''
Function:
    Implementation of YouTubeVideoClient
Author:
    Zhenchao Jin
WeChat Official Account (微信公众号):
    Charles的皮卡丘
'''
import os
import requests
from contextlib import suppress
from .base import BaseVideoClient
from ..utils.youtubeutils import YouTube
from urllib.parse import parse_qs, urlparse
from ..utils import legalizestring, useparseheaderscookies, yieldtimerelatedtitle, safeextractfromdict, resp2json, floatornone, VideoInfo


class YouTubeVideoClient(BaseVideoClient):
    source = 'YouTubeVideoClient'
    
    def __init__(self, **kwargs):
        super(YouTubeVideoClient, self).__init__(**kwargs)
        # 建议后续将这里改为随机 User-Agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.default_parse_headers = {"user-agent": user_agent}
        self.default_download_headers = {"user-agent": user_agent}
        self.default_headers = self.default_parse_headers
        self._initsession()

    def _parsefromurlwithytdown(self, url: str, request_overrides: dict = None) -> list[VideoInfo]:
        if not self.belongto(url=url): 
            return []
            
        request_overrides = request_overrides or {}
        video_info = VideoInfo(source=self.source)
        null_backup_title = yieldtimerelatedtitle(self.source)
        vid = parse_qs(urlparse(url).query, keep_blank_values=True)['v'][0]
        
        headers = {
            "origin": "https://app.ytdown.to", 
            "referer": "https://app.ytdown.to/en27/", 
            "sec-ch-ua": "\"Google Chrome\";v=\"120\", \"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"120\"", 
            "sec-ch-ua-mobile": "?0", 
            "sec-ch-ua-platform": "\"Windows\"", 
            "sec-fetch-dest": "empty", 
            "sec-fetch-mode": "cors", 
            "sec-fetch-site": "same-origin", 
            "user-agent": self.default_parse_headers["user-agent"]
        }
        
        try:
            resp = requests.post('https://app.ytdown.to/proxy.php', data={'url': url}, headers=headers, **request_overrides)
            resp.raise_for_status()
            raw_data = resp2json(resp=resp)
            video_info.update(dict(raw_data=raw_data))
            
            # 分离并排序视频与音频媒体
            media_items = raw_data.get('api', {}).get('mediaItems', [])
            
            video_medias = [i for i in media_items if isinstance(i, dict) and str(i.get('type')).lower() == 'video' and str(i.get('mediaUrl')).startswith('http')]
            video_medias = sorted(video_medias, key=lambda item: floatornone(str(item.get('mediaFileSize')).split(' ')[0]), reverse=True)
            
            audio_medias = [i for i in media_items if isinstance(i, dict) and str(i.get('type')).lower() == 'audio' and str(i.get('mediaUrl')).startswith('http')]
            audio_medias = sorted(audio_medias, key=lambda item: floatornone(str(item.get('mediaFileSize')).split(' ')[0]), reverse=True)
            
            download_url, ext, download_url_can_be_visited = None, None, False
            audio_download_url, audio_ext, audio_download_url_can_be_visited = None, None, False
            
            # 寻找可用视频链接
            for video_media in video_medias:
                resp = requests.post('https://app.ytdown.to/proxy.php', data={'url': video_media['mediaUrl']}, headers=headers, **request_overrides)
                resp.raise_for_status()
                
                download_url = resp2json(resp=resp)['api']['fileUrl']
                ext = str(video_media['mediaExtension']).lower()
                
                stream_headers = headers.copy()
                stream_headers.update({"Range": "bytes=0-0"})
                
                try:
                    test_resp = requests.get(download_url, stream=True, headers=stream_headers, allow_redirects=True, verify=False, **request_overrides)
                    test_resp.raise_for_status()
                    download_url_can_be_visited = True
                    break
                except Exception:
                    continue
                    
            # 寻找可用音频链接
            for audio_media in audio_medias:
                resp = requests.post('https://app.ytdown.to/proxy.php', data={'url': audio_media['mediaUrl']}, headers=headers, **request_overrides)
                resp.raise_for_status()
                
                audio_download_url = resp2json(resp=resp)['api']['fileUrl']
                audio_ext = str(audio_media['mediaExtension']).lower()
                
                stream_headers = headers.copy()
                stream_headers.update({"Range": "bytes=0-0"})
                
                try:
                    test_resp = requests.get(audio_download_url, stream=True, headers=stream_headers, allow_redirects=True, verify=False, **request_overrides)
                    test_resp.raise_for_status()
                    audio_download_url_can_be_visited = True
                    break
                except Exception:
                    continue
                    
            if not download_url_can_be_visited or not audio_download_url_can_be_visited: 
                return []
                
            video_info.update(dict(
                download_url=download_url, 
                ext=ext, 
                audio_download_url=audio_download_url, 
                audio_ext=audio_ext, 
                default_download_headers=headers, 
                default_audio_download_headers=headers
            ))
            
            raw_title = safeextractfromdict(raw_data, ['api', 'title'], None) or null_backup_title
            video_title = legalizestring(raw_title, replace_null_string=null_backup_title).removesuffix('.')
            
            video_info.update(dict(
                title=video_title, 
                save_path=os.path.join(self.work_dir, self.source, f'{video_title}.{ext}'), 
                audio_save_path=os.path.join(self.work_dir, self.source, f'{video_title}.audio.{audio_ext}'), 
                identifier=vid, 
                cover_url=safeextractfromdict(raw_data, ['api', 'imagePreviewUrl'], None)
            ))
            
        except Exception as err:
            err_msg = f'{self.source}._parsefromurlwithytdown >>> {url} (Error: {err})'
            video_info.update(dict(err_msg=err_msg))
            self.logger_handle.error(err_msg, disable_print=self.disable_print)
            
        return [video_info]

    def _parsefromurlwithdownr(self, url: str, request_overrides: dict = None) -> list[VideoInfo]:
        if not self.belongto(url=url): 
            return []
            
        request_overrides = request_overrides or {}
        video_info = VideoInfo(source=self.source)
        null_backup_title = yieldtimerelatedtitle(self.source)
        vid = parse_qs(urlparse(url).query, keep_blank_values=True)['v'][0]
        
        headers = {
            "user-agent": self.default_parse_headers["user-agent"], 
            "referer": "https://downr.org/"
        }
        
        try:
            init_resp = requests.get('https://downr.org/.netlify/functions/analytics', headers=headers, **request_overrides)
            cookies = requests.utils.dict_from_cookiejar(init_resp.cookies)
            
            resp = requests.post('https://downr.org/.netlify/functions/nyt', headers=headers, cookies=cookies, json={"url": url}, **request_overrides)
            resp.raise_for_status()
            
            raw_data = resp2json(resp=resp)
            video_info.update(dict(raw_data=raw_data))
            
            medias = raw_data.get('medias', [])
            video_medias = [item for item in medias if item.get('type') == 'video']
            video_medias = sorted(video_medias, key=lambda item: (item.get('height', 0) * item.get('width', 0), item.get('bitrate', 0)), reverse=True)
            
            audio_medias = [item for item in medias if item.get('type') == 'audio']
            audio_medias = sorted(audio_medias, key=lambda item: (item.get('bitrate', 0), float(item.get('audioSampleRate') or 0)), reverse=True)
            
            download_url, ext, download_url_can_be_visited = None, None, False
            audio_download_url, audio_ext, audio_download_url_can_be_visited = None, None, False
            
            for video_media in video_medias:
                download_url = video_media['url']
                ext = video_media['ext']
                
                stream_headers = headers.copy()
                stream_headers.update({"Range": "bytes=0-0"})
                
                try:
                    test_resp = requests.get(download_url, stream=True, headers=stream_headers, allow_redirects=True, verify=False, **request_overrides)
                    test_resp.raise_for_status()
                    download_url_can_be_visited = True
                    break
                except Exception:
                    continue
                    
            for audio_media in audio_medias:
                audio_download_url = audio_media['url']
                audio_ext = audio_media['ext']
                
                stream_headers = headers.copy()
                stream_headers.update({"Range": "bytes=0-0"})
                
                try:
                    test_resp = requests.get(audio_download_url, stream=True, headers=stream_headers, allow_redirects=True, verify=False, **request_overrides)
                    test_resp.raise_for_status()
                    audio_download_url_can_be_visited = True
                    break
                except Exception:
                    continue
                    
            if not download_url_can_be_visited or not audio_download_url_can_be_visited: 
                return []
                
            video_info.update(dict(
                download_url=download_url, 
                ext=ext, 
                audio_download_url=audio_download_url, 
                audio_ext=audio_ext, 
                default_download_headers=headers, 
                default_audio_download_headers=headers
            ))
            
            raw_title = safeextractfromdict(raw_data, ['title'], None) or null_backup_title
            video_title = legalizestring(raw_title, replace_null_string=null_backup_title).removesuffix('.')
            
            video_info.update(dict(
                title=video_title, 
                save_path=os.path.join(self.work_dir, self.source, f'{video_title}.{ext}'), 
                audio_save_path=os.path.join(self.work_dir, self.source, f'{video_title}.audio.{audio_ext}'), 
                identifier=vid, 
                cover_url=safeextractfromdict(raw_data, ['thumbnail'], None)
            ))
            
        except Exception as err:
            err_msg = f'{self.source}._parsefromurlwithdownr >>> {url} (Error: {err})'
            video_info.update(dict(err_msg=err_msg))
            self.logger_handle.error(err_msg, disable_print=self.disable_print)
            
        return [video_info]

    @useparseheaderscookies
    def parsefromurl(self, url: str, request_overrides: dict = None) -> list[VideoInfo]:
        if not self.belongto(url=url): 
            return []
            
        request_overrides = request_overrides or {}
        video_info = VideoInfo(source=self.source)
        null_backup_title = yieldtimerelatedtitle(self.source)
        
        # 修复了重复调用 _parsefromurlwithytdown 的 Bug
        for parser in [self._parsefromurlwithytdown, self._parsefromurlwithdownr]:
            video_infos = parser(url, request_overrides)
            if any(info.with_valid_download_url for info in (video_infos or [])): 
                return video_infos
                
        # 官方接口兜底
        try:
            vid = parse_qs(urlparse(url).query, keep_blank_values=True)['v'][0]
            yt = YouTube(video_id=vid)
            
            raw_data = yt.vid_info
            video_info.update(dict(raw_data=raw_data))
            
            download_url = yt.streams.gethighestresolution()
            video_info.update(dict(download_url=download_url))
            
            video_title = legalizestring(yt.title, replace_null_string=null_backup_title).removesuffix('.')
            cover_url = safeextractfromdict(raw_data, ['videoDetails', 'thumbnail', 'thumbnails', -1, 'url'], None)
            
            video_info.update(dict(
                title=video_title, 
                save_path=os.path.join(self.work_dir, self.source, f'{video_title}.mp4'), 
                ext='mp4', 
                identifier=vid, 
                cover_url=cover_url
            ))
            
        except Exception as err:
            err_msg = f'{self.source}.parsefromurl >>> {url} (Error: {err})'
            video_info.update(dict(err_msg=err_msg))
            self.logger_handle.error(err_msg, disable_print=self.disable_print)
            
        return [video_info]

    @staticmethod
    def belongto(url: str, valid_domains: list[str] | set[str] = None):
        valid_domains = set(valid_domains or []) | {"youtube.com"}
        return BaseVideoClient.belongto(url, valid_domains)