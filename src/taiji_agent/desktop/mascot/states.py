"""吉祥物状态定义"""
from enum import Enum


class MascotState(Enum):
    """吉祥物状态"""
    IDLE = "idle"
    THINKING = "thinking"
    SPEAKING = "speaking"
    LISTENING = "listening"
    WAITING = "waiting"
    SLEEPING = "sleeping"


MASCOT_COLORS = {
    MascotState.IDLE: "#81C784",
    MascotState.THINKING: "#4CAF50",
    MascotState.SPEAKING: "#00E676",
    MascotState.LISTENING: "#66BB6A",
    MascotState.WAITING: "#A5D6A7",
    MascotState.SLEEPING: "#2E7D32",
}

MASCOT_LOTTIE_FILES = {
    MascotState.IDLE: "idle.json",
    MascotState.THINKING: "thinking.json",
    MascotState.SPEAKING: "speaking.json",
    MascotState.SLEEPING: "sleeping.json",
}

MASCOT_EMOJIS = {
    MascotState.IDLE: "🟢",
    MascotState.THINKING: "💭",
    MascotState.SPEAKING: "🗣️",
    MascotState.LISTENING: "👂",
    MascotState.WAITING: "⏳",
    MascotState.SLEEPING: "😴",
}
