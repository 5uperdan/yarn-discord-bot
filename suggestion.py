from dataclasses import dataclass


@dataclass
class Suggestion:

    author: object
    content: str
    bot_msg_uid: int

    def __hash__(self):
        return hash(self.bot_msg_uid)

    def __eq__(self, other):
        if self.bot_msg_uid == other.bot_msg_uid:
            return True
        return False
