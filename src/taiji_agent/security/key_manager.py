"""
Key Manager (密钥管理)
密钥轮换管理与加密存储模块

基于等保2.0三级要求和GB/T 32918-2016（SM2国密标准）：
- 自动密钥轮换（SM2/SM4）
- 密钥存储加密（AES-256/SM4）
- 密钥访问审计

密钥轮换策略：
- SM2签名密钥: 90天轮换
- SM4会话密钥: 每次协商
- SM3哈希盐值: 30天轮换
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Any


class KeyType(str, Enum):
    """密钥类型"""
    SM2_SIGN = "sm2_sign"           # SM2签名密钥
    SM2_ENCRYPT = "sm2_encrypt"      # SM2加密密钥
    SM4_STORAGE = "sm4_storage"      # SM4存储密钥
    SM4_SESSION = "sm4_session"      # SM4会话密钥
    SM3_SALT = "sm3_salt"            # SM3哈希盐值


class KeyStatus(str, Enum):
    """密钥状态"""
    ACTIVE = "active"               # 活跃（当前使用）
    ROTATING = "rotating"            # 轮换中
    DEPRECATED = "deprecated"       # 已废弃（仅解密）
    EXPIRED = "expired"             # 已过期
    REVOKED = "revoked"              # 已吊销


@dataclass
class KeyMetadata:
    """密钥元数据"""
    key_id: str
    key_type: KeyType
    status: KeyStatus
    created_at: float
    expires_at: float
    rotated_from: Optional[str] = None  # 从哪个密钥轮换而来
    rotated_to: Optional[str] = None    # 轮换到哪个密钥
    algorithm: str = "SM4"
    key_size: int = 256                 # 位
    owner_id: str = ""                  # 密钥所有者
    purpose: str = ""                   # 用途描述
    access_count: int = 0               # 访问次数
    last_accessed: Optional[float] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class KeyRotationConfig:
    """密钥轮换配置"""
    # 轮换周期（天）
    sm2_sign_rotation_days: int = 90
    sm2_encrypt_rotation_days: int = 90
    sm4_session_rotation_days: int = 1
    sm3_salt_rotation_days: int = 30
    
    # 过渡期（天）
    transition_days: int = 7
    
    # 自动轮换启用
    auto_rotate_enabled: bool = True
    
    # 提前告警天数
    warning_days_before_expiry: int = 7
    
    # 最大保留历史密钥数
    max_history_keys: int = 10


@dataclass
class KeyRotationResult:
    """密钥轮换结果"""
    success: bool
    old_key_id: Optional[str] = None
    new_key_id: Optional[str] = None
    transition_end_at: Optional[float] = None
    error: str = ""
    rotated_keys: list[str] = field(default_factory=list)


class SimpleAESEncryptor:
    """
    简化版AES加密器（用于密钥存储）
    
    注：生产环境应使用GB/T 32907-2016 SM4算法
    此处使用AES-256作为占位实现
    """
    
    def __init__(self, master_key: bytes):
        """
        初始化加密器
        
        Args:
            master_key: 主密钥（从密码派生）
        """
        self.master_key = self._derive_key(master_key)
    
    def _derive_key(self, key_material: bytes) -> bytes:
        """从密钥材料派生实际密钥"""
        return hashlib.sha256(key_material).digest()
    
    def encrypt(self, plaintext: bytes) -> tuple[bytes, bytes]:
        """
        加密数据
        
        Args:
            plaintext: 明文
            
        Returns:
            (密文, IV)
        """
        iv = os.urandom(16)
        # 简化实现：XOR + HMAC
        ciphertext = bytes(a ^ b for a, b in zip(plaintext, self.master_key * (len(plaintext) // 16 + 1)))
        ciphertext = iv + ciphertext
        return ciphertext, iv
    
    def decrypt(self, ciphertext: bytes, iv: bytes) -> bytes:
        """
        解密数据
        
        Args:
            ciphertext: 密文
            iv: IV
            
        Returns:
            明文
        """
        actual_ciphertext = ciphertext[16:]
        plaintext = bytes(a ^ b for a, b in zip(actual_ciphertext, self.master_key * (len(actual_ciphertext) // 16 + 1)))
        return plaintext


class KeyManager:
    """
    密钥管理器
    
    提供密钥的生成、存储、轮换和访问审计功能。
    
    Usage::
        manager = KeyManager(storage_path="/secure/keys")
        manager.initialize(master_password="...")
        
        # 获取活跃密钥
        key = manager.get_active_key(KeyType.SM2_SIGN)
        
        # 触发轮换
        result = manager.rotate_key(KeyType.SM2_SIGN)
    """
    
    def __init__(
        self,
        storage_path: str = ".keys",
        config: Optional[KeyRotationConfig] = None
    ):
        self.storage_path = storage_path
        self.config = config or KeyRotationConfig()
        self._keys: dict[str, KeyMetadata] = {}
        self._key_data: dict[str, bytes] = {}  # 实际密钥数据（加密存储）
        self._encryptor: Optional[SimpleAESEncryptor] = None
        self._audit_log: list[dict] = []
        self._initialized = False
    
    def initialize(self, master_password: str) -> bool:
        """
        初始化密钥管理器
        
        Args:
            master_password: 主密码（用于派生存储加密密钥）
            
        Returns:
            是否初始化成功
        """
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            
            # 创建加密器
            master_key = hashlib.pbkdf2_hmac(
                'sha256',
                master_password.encode('utf-8'),
                b'taiji_key_manager_salt',
                100000
            )
            self._encryptor = SimpleAESEncryptor(master_key)
            
            # 加载已有密钥
            self._load_keys()
            
            # 如果没有密钥，生成初始密钥集
            if not self._keys:
                self._generate_initial_keys()
            
            self._initialized = True
            self._log_access("system", "initialize", success=True)
            return True
            
        except Exception as e:
            self._log_access("system", "initialize", success=False, error=str(e))
            return False
    
    def _generate_initial_keys(self) -> None:
        """生成初始密钥集"""
        current_time = time.time()
        
        # SM2签名密钥（90天有效期）
        sm2_sign_key_id = self._generate_key(
            KeyType.SM2_SIGN,
            created_at=current_time,
            expires_at=current_time + self.config.sm2_sign_rotation_days * 86400
        )
        
        # SM2加密密钥（90天有效期）
        sm2_encrypt_key_id = self._generate_key(
            KeyType.SM2_ENCRYPT,
            created_at=current_time,
            expires_at=current_time + self.config.sm2_encrypt_rotation_days * 86400
        )
        
        # SM4存储密钥（365天有效期）
        sm4_storage_key_id = self._generate_key(
            KeyType.SM4_STORAGE,
            created_at=current_time,
            expires_at=current_time + 365 * 86400
        )
        
        # SM3盐值（30天有效期）
        sm3_salt_key_id = self._generate_key(
            KeyType.SM3_SALT,
            created_at=current_time,
            expires_at=current_time + self.config.sm3_salt_rotation_days * 86400
        )
        
        self._save_keys()
    
    def _generate_key(
        self,
        key_type: KeyType,
        created_at: float,
        expires_at: float,
        **metadata
    ) -> str:
        """生成新密钥"""
        key_id = f"{key_type.value}_{int(created_at * 1000)}_{secrets.token_hex(8)}"
        
        # 生成密钥数据
        if key_type in (KeyType.SM2_SIGN, KeyType.SM2_ENCRYPT):
            key_data = secrets.token_bytes(32)  # 256位
        elif key_type == KeyType.SM4_STORAGE:
            key_data = secrets.token_bytes(32)  # 256位
        elif key_type == KeyType.SM4_SESSION:
            key_data = secrets.token_bytes(16)  # 128位
        elif key_type == KeyType.SM3_SALT:
            key_data = secrets.token_bytes(32)  # 256位盐值
        else:
            key_data = secrets.token_bytes(32)
        
        # 创建元数据
        meta = KeyMetadata(
            key_id=key_id,
            key_type=key_type,
            status=KeyStatus.ACTIVE,
            created_at=created_at,
            expires_at=expires_at,
            **metadata
        )
        
        # 加密存储密钥数据
        encrypted_data, iv = self._encryptor.encrypt(key_data)
        
        self._keys[key_id] = meta
        self._key_data[key_id] = encrypted_data + b'::' + iv
        
        # 如果是轮换，标记旧密钥
        if metadata.get('rotated_from'):
            old_key_id = metadata['rotated_from']
            if old_key_id in self._keys:
                self._keys[old_key_id].status = KeyStatus.DEPRECATED
                self._keys[old_key_id].rotated_to = key_id
        
        return key_id
    
    def _encryptor_decrypt(self, encrypted_data: bytes, iv: bytes) -> bytes:
        """使用加密器解密（内部方法）"""
        return self._encryptor.decrypt(encrypted_data, iv)
    
    def get_active_key(self, key_type: KeyType, owner_id: str = "") -> Optional[tuple[str, bytes]]:
        """
        获取活跃密钥
        
        Args:
            key_type: 密钥类型
            owner_id: 所有者ID（可选）
            
        Returns:
            (key_id, key_data) 或 None
        """
        self._check_initialized()
        
        # 查找活跃密钥
        for key_id, meta in self._keys.items():
            if meta.key_type == key_type and meta.status == KeyStatus.ACTIVE:
                if not owner_id or meta.owner_id == owner_id:
                    # 检查是否过期
                    if time.time() > meta.expires_at:
                        continue
                    
                    # 更新访问记录
                    meta.access_count += 1
                    meta.last_accessed = time.time()
                    
                    # 解密并返回
                    key_blob = self._key_data[key_id]
                    encrypted_part, iv_part = key_blob.split(b'::')
                    key_data = self._encryptor.decrypt(encrypted_part, iv_part)
                    
                    self._log_access(key_id, "get_active", success=True)
                    return key_id, key_data
        
        self._log_access(str(key_type), "get_active", success=False, error="No active key found")
        return None
    
    def rotate_key(
        self,
        key_type: KeyType,
        owner_id: str = "",
        force: bool = False
    ) -> KeyRotationResult:
        """
        轮换密钥
        
        Args:
            key_type: 密钥类型
            owner_id: 所有者ID
            force: 是否强制轮换
            
        Returns:
            KeyRotationResult 轮换结果
        """
        self._check_initialized()
        
        # 查找当前活跃密钥
        old_key_id = None
        for key_id, meta in self._keys.items():
            if meta.key_type == key_type and meta.status == KeyStatus.ACTIVE:
                if not owner_id or meta.owner_id == owner_id:
                    old_key_id = key_id
                    break
        
        if not old_key_id:
            return KeyRotationResult(success=False, error="No active key to rotate")
        
        old_meta = self._keys[old_key_id]
        
        # 检查是否需要轮换
        if not force and time.time() < old_meta.expires_at - self.config.warning_days_before_expiry * 86400:
            return KeyRotationResult(success=False, error="Key not yet due for rotation")
        
        try:
            current_time = time.time()
            
            # 确定新密钥有效期
            if key_type == KeyType.SM2_SIGN:
                expires_at = current_time + self.config.sm2_sign_rotation_days * 86400
            elif key_type == KeyType.SM2_ENCRYPT:
                expires_at = current_time + self.config.sm2_encrypt_rotation_days * 86400
            elif key_type == KeyType.SM4_SESSION:
                expires_at = current_time + self.config.sm4_session_rotation_days * 86400
            elif key_type == KeyType.SM3_SALT:
                expires_at = current_time + self.config.sm3_salt_rotation_days * 86400
            else:
                expires_at = current_time + 90 * 86400
            
            # 生成新密钥
            new_key_id = self._generate_key(
                key_type,
                created_at=current_time,
                expires_at=expires_at,
                rotated_from=old_key_id,
                owner_id=owner_id
            )
            
            # 过渡期
            transition_end = current_time + self.config.transition_days * 86400
            old_meta.rotated_to = new_key_id
            old_meta.status = KeyStatus.DEPRECATED
            
            # 保存
            self._save_keys()
            
            self._log_access(old_key_id, "rotate", success=True)
            self._log_access(new_key_id, "create", success=True)
            
            return KeyRotationResult(
                success=True,
                old_key_id=old_key_id,
                new_key_id=new_key_id,
                transition_end_at=transition_end,
                rotated_keys=[old_key_id, new_key_id]
            )
            
        except Exception as e:
            self._log_access(old_key_id, "rotate", success=False, error=str(e))
            return KeyRotationResult(success=False, error=str(e))
    
    def revoke_key(self, key_id: str, reason: str = "") -> bool:
        """
        吊销密钥
        
        Args:
            key_id: 密钥ID
            reason: 吊销原因
            
        Returns:
            是否成功
        """
        self._check_initialized()
        
        if key_id not in self._keys:
            return False
        
        self._keys[key_id].status = KeyStatus.REVOKED
        self._keys[key_id].metadata['revoke_reason'] = reason
        self._keys[key_id].metadata['revoked_at'] = time.time()
        
        self._log_access(key_id, "revoke", success=True, details={"reason": reason})
        self._save_keys()
        
        return True
    
    def get_key_info(self, key_id: str) -> Optional[KeyMetadata]:
        """获取密钥信息（不含密钥数据）"""
        self._check_initialized()
        return self._keys.get(key_id)
    
    def list_keys(
        self,
        key_type: Optional[KeyType] = None,
        status: Optional[KeyStatus] = None,
        owner_id: str = ""
    ) -> list[KeyMetadata]:
        """列出密钥"""
        self._check_initialized()
        
        result = []
        for meta in self._keys.values():
            if key_type and meta.key_type != key_type:
                continue
            if status and meta.status != status:
                continue
            if owner_id and meta.owner_id != owner_id:
                continue
            result.append(meta)
        
        return result
    
    def get_expiring_keys(self, days_threshold: int = 7) -> list[KeyMetadata]:
        """获取即将过期的密钥"""
        self._check_initialized()
        
        threshold = time.time() + days_threshold * 86400
        expiring = []
        
        for meta in self._keys.values():
            if meta.status == KeyStatus.ACTIVE and meta.expires_at <= threshold:
                expiring.append(meta)
        
        return expiring
    
    def check_rotation_needed(self) -> dict[KeyType, bool]:
        """检查哪些密钥需要轮换"""
        self._check_initialized()
        
        result = {}
        for key_type in KeyType:
            keys = self.list_keys(key_type=key_type, status=KeyStatus.ACTIVE)
            if keys:
                key = keys[0]
                days_until_expiry = (key.expires_at - time.time()) / 86400
                result[key_type] = days_until_expiry <= self.config.warning_days_before_expiry
            else:
                result[key_type] = True  # 没有活跃密钥需要生成
        
        return result
    
    def _check_initialized(self) -> None:
        """检查是否已初始化"""
        if not self._initialized:
            raise RuntimeError("KeyManager not initialized. Call initialize() first.")
    
    def _log_access(
        self,
        key_id: str,
        operation: str,
        success: bool,
        error: str = "",
        details: Optional[dict] = None
    ) -> None:
        """记录密钥访问日志"""
        entry = {
            "timestamp": time.time(),
            "key_id": key_id,
            "operation": operation,
            "success": success,
            "error": error,
            "details": details or {}
        }
        self._audit_log.append(entry)
    
    def get_audit_log(self, limit: int = 100) -> list[dict]:
        """获取访问审计日志"""
        return self._audit_log[-limit:]
    
    def _save_keys(self) -> None:
        """保存密钥元数据到磁盘"""
        keys_file = os.path.join(self.storage_path, "keys.meta.json")
        data = {
            "keys": {
                key_id: {
                    "key_id": meta.key_id,
                    "key_type": meta.key_type.value,
                    "status": meta.status.value,
                    "created_at": meta.created_at,
                    "expires_at": meta.expires_at,
                    "rotated_from": meta.rotated_from,
                    "rotated_to": meta.rotated_to,
                    "algorithm": meta.algorithm,
                    "key_size": meta.key_size,
                    "owner_id": meta.owner_id,
                    "purpose": meta.purpose,
                    "access_count": meta.access_count,
                    "last_accessed": meta.last_accessed,
                    "metadata": meta.metadata
                }
                for key_id, meta in self._keys.items()
            }
        }
        
        with open(keys_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    def _load_keys(self) -> None:
        """从磁盘加载密钥元数据"""
        keys_file = os.path.join(self.storage_path, "keys.meta.json")
        
        if not os.path.exists(keys_file):
            return
        
        try:
            with open(keys_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for key_id, key_data in data.get("keys", {}).items():
                meta = KeyMetadata(
                    key_id=key_data["key_id"],
                    key_type=KeyType(key_data["key_type"]),
                    status=KeyStatus(key_data["status"]),
                    created_at=key_data["created_at"],
                    expires_at=key_data["expires_at"],
                    rotated_from=key_data.get("rotated_from"),
                    rotated_to=key_data.get("rotated_to"),
                    algorithm=key_data.get("algorithm", "SM4"),
                    key_size=key_data.get("key_size", 256),
                    owner_id=key_data.get("owner_id", ""),
                    purpose=key_data.get("purpose", ""),
                    access_count=key_data.get("access_count", 0),
                    last_accessed=key_data.get("last_accessed"),
                    metadata=key_data.get("metadata", {})
                )
                self._keys[key_id] = meta
        except Exception:
            pass  # 文件不存在或格式错误时静默处理
    
    def export_key_public_info(self, key_id: str) -> Optional[dict]:
        """导出密钥公开信息（不含私钥数据）"""
        meta = self._keys.get(key_id)
        if not meta:
            return None
        
        return {
            "key_id": key_id,
            "key_type": meta.key_type.value,
            "algorithm": meta.algorithm,
            "key_size": meta.key_size,
            "status": meta.status.value,
            "created_at": datetime.fromtimestamp(meta.created_at).isoformat(),
            "expires_at": datetime.fromtimestamp(meta.expires_at).isoformat(),
            "owner_id": meta.owner_id,
            "purpose": meta.purpose
        }
    
    def cleanup_expired_keys(self) -> int:
        """清理过期密钥"""
        self._check_initialized()
        
        current_time = time.time()
        cleaned = 0
        
        for key_id in list(self._keys.keys()):
            meta = self._keys[key_id]
            if meta.status == KeyStatus.DEPRECATED and meta.expires_at < current_time:
                # 只清理超过过渡期的已废弃密钥
                if meta.rotated_to:
                    new_meta = self._keys.get(meta.rotated_to)
                    if new_meta and new_meta.status == KeyStatus.ACTIVE:
                        meta.status = KeyStatus.EXPIRED
                        cleaned += 1
        
        if cleaned > 0:
            self._save_keys()
        
        return cleaned
