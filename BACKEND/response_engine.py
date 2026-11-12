import random


class VENResponseEngine:
    def __init__(self, choose=None):
        self.choose = choose or random.choice
        self.last_responses = {}

    def choose_response(self, key, choices):
        previous = self.last_responses.get(key)
        available = [choice for choice in choices if choice != previous]
        response = self.choose(available or choices)
        self.last_responses[key] = response
        return response

    def respond_to_intent(self, intent, message=""):
        normalized = message.lower()

        if intent == "greeting":
            if "how are you" in normalized:
                choices = [
                    "I'm here and ready to help. How are you doing?",
                    "Doing well, thanks for asking. What's on your mind?",
                    "I'm ready to chat. How has your day been?",
                    "All good here. What would you like to talk about?",
                ]
            else:
                choices = [
                    "Hey! What would you like to talk about?",
                    "Hi there. What's on your mind?",
                    "Hello! How can I make your day a little easier?",
                    "Hey, good to hear from you. What are you thinking about?",
                ]
        elif intent == "gratitude":
            choices = [
                "You're welcome. What else can I help with?",
                "Anytime—I'm glad that helped.",
                "Of course! Let me know what you'd like to do next.",
            ]
        elif intent == "farewell":
            choices = [
                "See you later. I'll be here when you need me.",
                "Take care, and have a good one!",
                "Bye for now. I enjoyed our chat.",
            ]
        elif intent == "identity":
            choices = [
                "I'm VEN, your personal assistant. I can chat, use my local knowledge, and look up public web results.",
                "My name is VEN. I'm here to help you think through questions and find information.",
            ]
        else:
            choices = [
                "Sure—tell me what you're working on, and we'll figure it out together.",
                "I'm listening. What would you like help with?",
                "Absolutely. Share a little more about what you need.",
            ]

        return self.choose_response(intent, choices)

    def respond_to_statement(self, message, result):
        meaning = result.get("meaning", {})
        propositions = meaning.get("propositions", [])
        if not propositions:
            return self.choose_response(
                "unclear_statement",
                [
                    f"I hear you: {message.strip()} What part of that would you like to explore?",
                    f"That's something to think about. What brought it to mind?",
                    "I'm following. Can you tell me a little more about what you mean?",
                ],
            )

        proposition = propositions[0]
        subject = proposition.get("subject") or ""
        relation = proposition.get("relation") or ""
        object_word = proposition.get("object") or ""
        if result.get("decision") == "contradiction":
            return self.choose_response(
                "contradiction",
                [
                    "I remember something that may conflict with that. Could you help me understand the difference?",
                    "That seems different from something I learned earlier. Which version should I keep in mind?",
                ],
            )

        if proposition.get("negation"):
            return self.choose_response(
                "negative_statement",
                [
                    f"So you don't {relation} {object_word}. What shaped that view?",
                    f"I hear you saying you don't {relation} {object_word}. Want to tell me more?",
                ],
            )

        if subject in ("i", "me", "myself") and relation == "has_property":
            if object_word in {
                "awesome", "calm", "cool", "excited", "fine", "good",
                "great", "happy", "proud", "relaxed", "wonderful",
            }:
                choices = [
                    f"You sound upbeat! What has you feeling {object_word}?",
                    f"Nice, you're feeling {object_word}. What made your day?",
                    f"Glad to hear you're {object_word}. What brought that on?",
                ]
            elif object_word in {
                "angry", "anxious", "bad", "exhausted", "sad", "stressed",
                "tired", "upset", "worried",
            }:
                choices = [
                    f"I'm sorry you're feeling {object_word}. Want to talk about what's going on?",
                    f"That sounds tough. What has been making you feel {object_word}?",
                    f"I hear you. Would it help to tell me a little more about feeling {object_word}?",
                ]
            else:
                choices = [
                    f"So you're feeling {object_word}. What brought that to mind?",
                    f"I hear you describing yourself as {object_word}. Want to say more?",
                    f"Got it—you feel {object_word}. How is that affecting your day?",
                ]
            return self.choose_response("personal_property", choices)

        if subject in ("i", "me", "myself") and object_word:
            action = relation.replace("_", " ")
            return self.choose_response(
                "personal_action",
                [
                    f"So you {action} {object_word}. What do you enjoy most about it?",
                    f"Interesting—you {action} {object_word}. How did you get into that?",
                    f"Got it, {object_word} is something you {action}. What made you bring it up?",
                ],
            )

        statement = message.strip().rstrip(".!?")
        return self.choose_response(
            "general_statement",
            [
                f"That's interesting: {statement}. What made you think of it?",
                f"Got it—you said, “{statement}.” What else should I know about that?",
                f"I'll keep that in mind: {statement}. How did you come to that conclusion?",
            ],
        )

    def respond_to_unknown_question(self, message):
        return self.choose_response(
            "unknown_question",
            [
                f"I couldn't find a reliable answer to “{message.strip()}.” Could you try asking it another way?",
                f"I don't have enough information to answer “{message.strip()}” confidently. Which part matters most?",
                f"I'm not finding a solid answer for “{message.strip()}” yet. Can you add a little context?",
            ],
        )

    def respond_to_missing_example_topic(self):
        return self.choose_response(
            "missing_example_topic",
            [
                "Sure—which word or idea should I use for the example?",
                "What would you like an example of?",
                "Tell me the word or topic, and I'll make an example for it.",
            ],
        )
