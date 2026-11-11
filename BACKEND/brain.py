
class VENBrain:

    def __init__(self):
        self.name = "VEN"

    def think(self, message):
        message = message.lower().strip()

        if not message:
            return "You haven't said anything yet."

        if "hello" in message or "hi" in message:
            return "Hello! I am VEN. It is nice to talk with you."

        if "how are you" in message:
            return "I am doing well. Thank you for asking."

        if "your name" in message:
            return "My name is VEN."

        if "who created" in message:
            return "I am being developed and trained by Al-hunter."

        return "I am still learning. I don't understand that yet."
