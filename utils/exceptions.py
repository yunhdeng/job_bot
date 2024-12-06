class JobBotException(Exception):
    """基础异常类"""
    pass

class CookieExpiredException(JobBotException):
    """Cookie过期异常"""
    pass

class DeliveryLimitExceedException(JobBotException):
    """投递限制异常"""
    pass

class JobBotError(Exception):
    """基础异常类"""
    pass

class LoginError(JobBotError):
    """登录相关错误"""
    pass

class DeliveryError(JobBotError):
    """投递相关错误"""
    pass

class LimitExceededError(JobBotError):
    """超出限制错误"""
    pass

class ProxyError(JobBotError):
    """代理相关错误"""
    pass 