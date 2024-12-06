import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger(level='INFO'):
    logger = logging.getLogger('JobBot')
    logger.setLevel(level)
    
    # 创建日志目录
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # 按日期分割日志文件
    date_str = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(log_dir, f'jobbot_{date_str}.log')
    
    # 文件处理器
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger 