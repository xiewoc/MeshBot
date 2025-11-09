from meshbot.config.config_loader import _config_manager
from meshbot.localizations.localization import MESSAGES

class I18N:
    def __init__(self):
        self.language = ""
        self.messages = MESSAGES.get(self.language, MESSAGES['zh_CN'])
    
    def gettext(self, key: str, **kwargs) -> str:
        """获取本地化消息，支持格式化参数"""
        if self.language:
            pass
        else:
            self.language = _config_manager.language

        message_template = self.messages.get(key, key)
        
        # 如果有参数，进行格式化
        if kwargs:
            try:
                return message_template.format(**kwargs)
            except KeyError as e:
                return f"[Format error in '{key}': missing {e}]"
        
        return message_template

i18n = I18N()
