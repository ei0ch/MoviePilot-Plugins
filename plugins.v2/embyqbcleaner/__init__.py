import os
import json
import time
import logging
import requests
import qbittorrentapi
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType, EventType


class EmbyQbCleaner(_PluginBase):
    # 插件名称
    plugin_name = "Emby播放清理"
    # 插件描述
    plugin_desc = "监听Emby媒体播放事件，自动清理对应的qBittorrent种子。"
    # 插件图标
    plugin_icon = "embyqbcleaner.png"
    # 插件版本
    plugin_version = "1.0.9"
    # 插件作者
    plugin_author = "aech"
    # 作者主页
    author_url = ""
    # 插件配置项ID前缀
    plugin_config_prefix = "embyqbcleaner_"
    # 加载顺序
    plugin_order = 10
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _emby_host = ""
    _emby_api_key = ""
    _emby_username = ""
    _emby_password = ""
    _qb_host = ""
    _qb_username = ""
    _qb_password = ""
    _telegram_token = ""
    _telegram_chat_id = ""
    _target_library = ""
    _delete_files = True
    _send_notification = True

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled", False)
            self._emby_host = config.get("emby_host", "")
            self._emby_api_key = config.get("emby_api_key", "")
            self._emby_username = config.get("emby_username", "")
            self._emby_password = config.get("emby_password", "")
            self._qb_host = config.get("qb_host", "")
            self._qb_username = config.get("qb_username", "")
            self._qb_password = config.get("qb_password", "")
            self._telegram_token = config.get("telegram_token", "")
            self._telegram_chat_id = config.get("telegram_chat_id", "")
            self._target_library = config.get("target_library", "")
            self._delete_files = config.get("delete_files", True)
            self._send_notification = config.get("send_notification", True)

    def get_command(self) -> List[Dict[str, Any]]:
        """
        定义远程控制命令
        """
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        """
        定义API接口
        """
        return [
            {
                "path": "/process_webhook",
                "endpoint": self.process_webhook,
                "methods": ["POST"],
                "summary": "处理Emby Webhook"
            }
        ]

    def process_webhook(self, data: dict):
        """
        处理Emby Webhook请求
        """
        if not self._enabled:
            return {"status": "error", "message": "插件未启用"}
        
        try:
            event = data.get("Event", "")
            
            # 处理播放相关事件
            if event in ["playback.stop", "item.played", "item.markplayed"]:
                self.process_media_item(data)
                return {"status": "success", "message": "事件已处理"}
            else:
                return {"status": "ignored", "message": f"不是播放相关事件: {event}"}
        except Exception as e:
            logger.error(f"处理webhook时出错: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'delete_files',
                                            'label': '删除文件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'send_notification',
                                            'label': '发送通知',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'emby_host',
                                            'label': 'Emby服务器地址',
                                            'placeholder': 'http://localhost:8096'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'emby_api_key',
                                            'label': 'Emby API密钥',
                                            'placeholder': '在Emby管理后台获取'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'emby_username',
                                            'label': 'Emby用户名',
                                            'placeholder': 'Emby登录用户名'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'emby_password',
                                            'label': 'Emby密码',
                                            'placeholder': 'Emby登录密码',
                                            'type': 'password'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'qb_host',
                                            'label': 'qBittorrent地址',
                                            'placeholder': 'http://localhost:8080'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'qb_username',
                                            'label': 'qBittorrent用户名',
                                            'placeholder': 'qBittorrent登录用户名'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'qb_password',
                                            'label': 'qBittorrent密码',
                                            'placeholder': 'qBittorrent登录密码',
                                            'type': 'password'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'target_library',
                                            'label': '目标媒体库',
                                            'placeholder': '要监控的Emby媒体库ID'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'telegram_token',
                                            'label': 'Telegram Bot Token',
                                            'placeholder': 'Telegram机器人Token'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'telegram_chat_id',
                                            'label': 'Telegram Chat ID',
                                            'placeholder': 'Telegram聊天ID'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '本插件需要在Emby端配置Webhook指向MoviePilot。当媒体播放完成时，将自动在qBittorrent中删除相应的种子。'
                                                    '如需使用Telegram通知，请填写相应的Bot Token和Chat ID。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "emby_host": "http://localhost:8096",
            "emby_api_key": "",
            "emby_username": "",
            "emby_password": "",
            "qb_host": "http://localhost:8080",
            "qb_username": "admin",
            "qb_password": "adminadmin",
            "telegram_token": "",
            "telegram_chat_id": "",
            "target_library": "",
            "delete_files": True,
            "send_notification": True
        }

    def get_page(self) -> List[dict]:
        """
        拼装插件详情页面
        """
        return []

    def get_state(self) -> bool:
        """
        获取插件状态
        """
        return self._enabled

    def stop_service(self):
        """
        退出插件
        """
        pass

    # 检查媒体项是否属于指定的媒体库
    def is_in_target_library(self, item_data):
        # 尝试从不同位置获取媒体库名称
        library_name = None
        
        # 尝试从嵌套字典中获取库名
        item = item_data.get("Item", {})
        if "CollectionType" in item:
            library_name = item.get("Name")
        elif "LibraryName" in item:
            library_name = item.get("LibraryName")
        elif "library" in item and isinstance(item["library"], dict):
            library_name = item["library"].get("Name")
        
        # 如果未找到库名，尝试从路径推断
        if not library_name:
            path = item.get("Path", "")
            if self._target_library.lower() in path.lower():
                return True
        
        # 如果找到库名，检查是否匹配目标库
        if library_name:
            return self._target_library.lower() in library_name.lower()
        
        # 默认不匹配
        return False

    # 获取Emby API令牌
    def get_emby_token(self):
        if self._emby_api_key:
            return self._emby_api_key
            
        url = f"{self._emby_host}/emby/Users/AuthenticateByName"
        headers = {
            "Content-Type": "application/json",
            "X-Emby-Authorization": "MediaBrowser Client=EmbyCleanup, Device=Server, DeviceId=1, Version=1.0.0"
        }
        data = {
            "Username": self._emby_username,
            "Pw": self._emby_password
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json().get("AccessToken")
        except Exception as e:
            logger.error(f"获取Emby令牌失败: {str(e)}")
            return None

    # 连接到qBittorrent
    def get_qb_client(self):
        try:
            qb = qbittorrentapi.Client(
                host=self._qb_host,
                username=self._qb_username,
                password=self._qb_password
            )
            qb.auth_log_in()
            return qb
        except Exception as e:
            logger.error(f"连接qBittorrent失败: {e}")
            return None

    # 根据媒体文件路径查找并删除种子
    def delete_torrent_by_file(self, file_path):
        logger.info(f"开始连接qBittorrent")
        qb = self.get_qb_client()
        if not qb:
            logger.error("连接qBittorrent失败")
            return False, "连接qBittorrent失败"
        
        try:
            # 获取所有种子
            torrents = qb.torrents_info()
            logger.info(f"当前共有 {len(torrents)} 个种子")
            
            # 从路径中提取文件名
            filename = os.path.basename(file_path)
            logger.info(f"查找包含文件的种子: {filename}")
            
            for torrent in torrents:
                # 先检查种子名称是否匹配
                if filename.lower() in torrent.name.lower():
                    logger.info(f"找到匹配的种子: {torrent.name}")
                    
                    # 获取种子详细信息
                    torrent_info = {
                        "name": torrent.name,
                        "added_on": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(torrent.added_on)),
                        "uploaded": round(torrent.uploaded / (1024**3), 2),  # 转换为GB
                        "tracker": torrent.tracker,
                        "tags": torrent.tags.split(', ') if torrent.tags else []
                    }
                    
                    try:
                        # 删除种子及其数据
                        qb.torrents_delete(delete_files=self._delete_files, hashes=torrent.hash)
                        logger.info(f"成功删除种子: {torrent.name}")
                        return True, torrent_info
                    except Exception as e:
                        logger.error(f"删除种子时出错: {str(e)}")
                        return False, f"删除种子失败: {str(e)}"
                
                # 如果名称不匹配，尝试检查文件列表
                try:
                    torrent_files = qb.torrents_files(torrent.hash)
                    for torrent_file in torrent_files:
                        torrent_filename = os.path.basename(torrent_file.name)
                        if filename.lower() == torrent_filename.lower():
                            logger.info(f"找到完全匹配的种子: {torrent.name}")
                            
                            # 获取种子详细信息
                            torrent_info = {
                                "name": torrent.name,
                                "added_on": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(torrent.added_on)),
                                "uploaded": round(torrent.uploaded / (1024**3), 2),  # 转换为GB
                                "tracker": torrent.tracker,
                                "tags": torrent.tags.split(', ') if torrent.tags else []
                            }
                            
                            try:
                                # 删除种子及其数据
                                qb.torrents_delete(delete_files=self._delete_files, hashes=torrent.hash)
                                logger.info(f"成功删除种子: {torrent.name}")
                                return True, torrent_info
                            except Exception as e:
                                logger.error(f"删除种子时出错: {str(e)}")
                                return False, f"删除种子失败: {str(e)}"
                except Exception as e:
                    continue
            
            logger.warning(f"未找到匹配的种子: {filename}")
            return False, "未找到匹配的种子"
        except Exception as e:
            logger.error(f"删除种子时出错: {str(e)}")
            return False, f"错误: {str(e)}"

    # 发送Telegram消息
    def send_telegram_notification(self, message, image_data=None):
        if not self._telegram_token or not self._telegram_chat_id or not self._send_notification:
            logger.warning("Telegram配置缺失或通知已禁用，跳过通知")
            return False
        
        try:
            logger.info("准备发送Telegram消息")
            if image_data:
                logger.info("发送带图片的消息")
                url = f"https://api.telegram.org/bot{self._telegram_token}/sendPhoto"
                data = {
                    "chat_id": self._telegram_chat_id,
                    "caption": message,
                    "parse_mode": "HTML"
                }
                files = {
                    "photo": ("image.jpg", image_data)
                }
                logger.info("发送请求到Telegram API")
                response = requests.post(url, data=data, files=files)
            else:
                logger.info("发送纯文本消息")
                url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
                data = {
                    "chat_id": self._telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                logger.info("发送请求到Telegram API")
                response = requests.post(url, data=data)
            
            response.raise_for_status()
            logger.info("Telegram消息发送成功")
            return True
        except Exception as e:
            logger.error(f"发送Telegram通知失败: {str(e)}")
            return False

    # 处理单个媒体项
    def process_media_item(self, item_data):
        try:
            logger.info("="*50)
            logger.info("开始处理新的媒体项")
            
            item = item_data.get("Item", {})
            item_name = item.get("Name", "未知")
            item_type = item.get("Type", "未知")
            file_path = item.get("Path", "")
            item_id = item.get("Id", "")
            
            if not file_path:
                logger.warning("数据中没有文件路径，跳过处理")
                return
            
            # 检查是否是目标库的媒体
            is_target = self.is_in_target_library(item_data) or self._target_library.lower() in file_path.lower()
            if not is_target:
                logger.info(f"忽略非目标媒体库的媒体: {item_name}")
                return
            
            # 获取封面图片URL
            image_url = None
            try:
                # 使用 Emby API 获取图片URL
                token = self.get_emby_token()
                if token:
                    image_url = f"{self._emby_host}/emby/Items/{item_id}/Images/Primary?api_key={token}"
            except Exception as e:
                logger.error(f"获取封面图片URL失败: {str(e)}")
            
            # 删除种子
            success, result = self.delete_torrent_by_file(file_path)
            
            # 准备通知消息
            notification = f"✅ <b>媒体清理</b>\n\n"
            notification += f"标题: <b>{item_name}</b>\n"
            notification += f"类型: {item_type}\n"
            
            if success and isinstance(result, dict):
                notification += f"种子名称: {result['name']}\n"
                notification += f"添加时间: {result['added_on']}\n"
                notification += f"上传流量: {result['uploaded']} GB\n"
                notification += f"Tracker: {result['tracker']}\n"
                if result['tags']:
                    notification += f"种子标签: {', '.join(result['tags'])}\n"
                notification += f"状态: ✓ 已删除\n"
            else:
                notification += f"状态: ✗ 失败\n"
                notification += f"详情: {result}"
            
            # 发送通知
            if self._send_notification:
                try:
                    # 使用 MoviePilot 的通知系统
                    self.post_message(
                        mtype=NotificationType.Plugin,
                        title="媒体清理通知",
                        text=notification.replace('<b>', '').replace('</b>', ''),
                        image=image_url  # 使用图片URL而不是二进制数据
                    )
                except Exception as e:
                    logger.error(f"发送通知失败: {str(e)}")
            
            logger.info("媒体项处理完成")
            logger.info("="*50)
            
        except Exception as e:
            logger.error(f"处理媒体项时出错: {str(e)}")
            logger.error("="*50)

    @eventmanager.register(EventType.WebhookMessage)
    def process_webhook_event(self, event: Event):
        """
        处理Webhook事件
        """
        if not self._enabled:
            return
        
        event_data = event.event_data
        if not event_data:
            return
            
        event_type = event_data.event
        
        # 处理播放相关事件
        if event_type in ["playback.stop", "item.played", "item.markplayed"]:
            logger.info(f"收到Emby播放事件: {event_type}")
            
            try:
                # 从事件数据中提取媒体信息
                item_data = {
                    "Event": event_type,
                    "Item": {
                        "Name": event_data.item_name,
                        "Path": event_data.item_path,
                        "Id": event_data.item_id,
                        "Type": event_data.media_type
                    }
                }
                
                # 处理媒体项
                self.process_media_item(item_data)
            except Exception as e:
                logger.error(f"处理Webhook事件出错: {str(e)}") 
