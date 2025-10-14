#!/usr/bin/env python3
"""
增强型日志系统 - 不删档、自动轮转、详细记录
"""
import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import json

class EnhancedLogger:
    def __init__(self, name, log_dir="./logs"):
        self.name = name
        self.log_dir = log_dir
        self.logger = logging.getLogger(name)
        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(f"{log_dir}/archive", exist_ok=True)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []
        self._setup_handlers()
    
    def _setup_handlers(self):
        # 1. 控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 2. 详细日志（按日期轮转，保留90天）
        detailed_log = f"{self.log_dir}/{self.name}_detailed.log"
        detailed_handler = TimedRotatingFileHandler(
            detailed_log, when='midnight', interval=1,
            backupCount=90, encoding='utf-8'
        )
        detailed_handler.setLevel(logging.DEBUG)
        detailed_handler.suffix = "%Y%m%d"
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        detailed_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(detailed_handler)
        
        # 3. 错误日志（50MB轮转）
        error_log = f"{self.log_dir}/{self.name}_errors.log"
        error_handler = RotatingFileHandler(
            error_log, maxBytes=50*1024*1024, backupCount=10, encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d]\n%(message)s\n' + '='*80,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)
        
        # 4. 审计日志（永久保存）
        audit_log = f"{self.log_dir}/audit_{datetime.now().strftime('%Y%m')}.log"
        audit_handler = logging.FileHandler(audit_log, encoding='utf-8')
        audit_handler.setLevel(logging.INFO)
        audit_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        audit_handler.setFormatter(audit_formatter)
        self.logger.addHandler(audit_handler)
    
    def get_logger(self):
        return self.logger
    
    def log_user_action(self, user_id, action, details=None):
        msg = f"[用户操作] user_id={user_id}, action={action}"
        if details:
            msg += f", details={details}"
        self.logger.info(msg)
    
    def log_api_call(self, api_name, params=None, response=None, error=None):
        msg = f"[API调用] {api_name}"
        if params:
            msg += f", params={params}"
        if error:
            self.logger.error(f"{msg}, error={error}")
        else:
            self.logger.info(msg)

def get_enhanced_logger(name="bot", log_dir="./logs"):
    return EnhancedLogger(name, log_dir).get_logger()
