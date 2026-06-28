"""太极 IM 集成 — 国内主流即时通讯平台

支持:
  - 飞书/Lark   (feishu)  ✅ 已有 gateway/feishu.py
  - 钉钉        (dingtalk)  ✅
  - 企业微信     (wecom)    ✅
  - 微信公众号   (weixin)   ✅
  - QQ          (qq)       ✅
"""
from taiji_agent.gateway.im.dingtalk import DingTalkGateway
from taiji_agent.gateway.im.wecom import WeComGateway
from taiji_agent.gateway.im.weixin import WeixinGateway
from taiji_agent.gateway.im.qq import QQGateway

__all__ = ["DingTalkGateway", "WeComGateway", "WeixinGateway", "QQGateway"]
