import datetime
import re

from kani import ChatRole
from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import relationship

from .db import Base


# ==== weather ====
class WeatherBiome(Base):
    __tablename__ = "weather_biomes"

    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    name = Column(String, nullable=False)
    city_id = Column(Integer, nullable=False)
    image_url = Column(String, nullable=True)
    temp_mod = Column(Integer, nullable=True)

    channels = relationship("WeatherChannelMap", back_populates="biome")

    def __repr__(self):
        return (
            f"<{type(self).__name__} id={self.id!r} guild_id={self.guild_id!r} name={self.name!r} "
            f"city_id={self.city_id!r} image_url={self.image_url!r}>"
        )


class WeatherChannelMap(Base):
    __tablename__ = "weather_channel_map"

    channel_id = Column(BigInteger, primary_key=True)
    biome_id = Column(Integer, ForeignKey("weather_biomes.id", ondelete="CASCADE"))

    biome = relationship("WeatherBiome", back_populates="channels")

    def __repr__(self):
        return f"<{type(self).__name__} id={self.id!r} biome_id={self.biome_id!r}>"


# ==== community goals ====
class CommunityGoal(Base):
    __tablename__ = "cg_goals"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    cost_cp = Column(Integer, nullable=False)
    funded_cp = Column(Integer, nullable=False, default=0)
    message_id = Column(BigInteger, nullable=True)
    description = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    log_channel_id = Column(BigInteger, nullable=True)
    contrib_channel_id = Column(BigInteger, nullable=True)

    contributions = relationship("CommunityGoalContribution", back_populates="goal")

    def to_avrae_dict(self):
        """Used to push CG data to avrae - not all fields represented here."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "cost_cp": self.cost_cp,
            "funded_cp": self.funded_cp,
            "message_id": self.message_id,
            "image_url": self.image_url,
            "log_channel_id": self.log_channel_id,
            "contrib_channel_id": self.contrib_channel_id,
        }


class CommunityGoalContribution(Base):
    __tablename__ = "cg_contributions"

    id = Column(Integer, primary_key=True)
    goal_id = Column(Integer, ForeignKey("cg_goals.id", ondelete="CASCADE"))
    user_id = Column(BigInteger, nullable=False)
    amount_cp = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    goal = relationship("CommunityGoal", back_populates="contributions")


# ==== encounters ====
class EncounterChannel(Base):
    __tablename__ = "enc_channels"

    channel_id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=False)
    desc = Column(String, nullable=False)
    recommended_level = Column(String, nullable=False)
    onward_travel = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    enc_table_name = Column(String, nullable=False)
    pinned_message_id = Column(BigInteger, nullable=False)


class RolledEncounter(Base):
    __tablename__ = "enc_encounter_log"

    id = Column(Integer, primary_key=True)
    channel_id = Column(BigInteger, nullable=False)
    author_id = Column(BigInteger, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    table_name = Column(String, nullable=False)
    tier = Column(String, nullable=False)
    rendered_text = Column(String, nullable=False)
    monster_ids = Column(String, nullable=True)  # comma-separated list of ids (ints)
    biome_name = Column(String, nullable=True)
    biome_text = Column(String, nullable=True)  # None if not in in-character channel (should be ignored in study)

    @property
    def rendered_text_nolinks(self):
        return re.sub(r"\[(.+?)]\(http.+?\)", r"\1", self.rendered_text)


class EncounterAdjustment(Base):
    __tablename__ = "enc_adjustments"

    id = Column(Integer, primary_key=True)
    until = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, index=True)
    table_name = Column(String, nullable=False)
    tier = Column(Integer, nullable=False)
    text = Column(String, nullable=False)  # the unrendered encounter text to deweight
    penalty = Column(Integer, nullable=False, default=1)


class EncounterOutbreak(Base):
    __tablename__ = "enc_outbreaks"

    id = Column(Integer, primary_key=True)
    channel_id = Column(BigInteger, nullable=False)
    until = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, index=True)
    table_name = Column(String, nullable=False)


# --- ai ---
class EncounterAISummary(Base):
    __tablename__ = "enc_summaries"

    id = Column(Integer, primary_key=True)
    encounter_id = Column(Integer, ForeignKey("enc_encounter_log.id", ondelete="CASCADE"))
    prompt = Column(String, nullable=False)
    generation = Column(String, nullable=False)
    hyperparams = Column(String, nullable=False)
    feedback = Column(Integer, nullable=True)
    prompt_version = Column(Integer, nullable=False)

    encounter = relationship("RolledEncounter")


class EncounterAISummaryFeedback(Base):
    __tablename__ = "enc_summaries_feedback"

    id = Column(Integer, primary_key=True)
    summary_id = Column(Integer, ForeignKey("enc_summaries.id", ondelete="CASCADE"))
    feedback = Column(String, nullable=False)
    edit = Column(String, nullable=False)

    summary = relationship("EncounterAISummary")


class EncounterAIBrainstormSession(Base):
    __tablename__ = "enc_brainstorms"

    id = Column(Integer, primary_key=True)
    encounter_id = Column(Integer, ForeignKey("enc_encounter_log.id", ondelete="CASCADE"))
    prompt = Column(String, nullable=False)
    hyperparams = Column(String, nullable=False)
    thread_id = Column(BigInteger, nullable=False)

    encounter = relationship("RolledEncounter")


class EncounterAIBrainstormMessage(Base):
    __tablename__ = "enc_brainstorm_messages"

    id = Column(Integer, primary_key=True)
    brainstorm_id = Column(Integer, ForeignKey("enc_brainstorms.id", ondelete="CASCADE"))
    role = Column(Enum(ChatRole), nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    brainstorm = relationship("EncounterAIBrainstormSession")


# ==== ai ====
class AIOpenEndedChat(Base):
    __tablename__ = "ai_chats"

    id = Column(Integer, primary_key=True)
    channel_id = Column(BigInteger, nullable=False)
    author_id = Column(BigInteger, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    prompt = Column(String, nullable=False)
    hyperparams = Column(String, nullable=False)
    thread_id = Column(BigInteger, nullable=False)
    thread_title = Column(String, nullable=True)


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("ai_chats.id", ondelete="CASCADE"))
    role = Column(Enum(ChatRole), nullable=False)
    content = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    chat = relationship("AIOpenEndedChat")


class AIFunctionCall(Base):
    __tablename__ = "ai_chat_function_calls"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("ai_chat_messages.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    arguments = Column(String, nullable=False)

    message = relationship("AIChatMessage")


# ==== message logging ====
class LoggedMessage(Base):
    __tablename__ = "logged_messages"

    id = Column(Integer, primary_key=True)
    # ids
    message_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    guild_id = Column(BigInteger, nullable=True)
    author_id = Column(BigInteger, nullable=False)
    parent_id = Column(BigInteger, nullable=True)  # channel parent id if thread
    # names
    channel_name = Column(String, nullable=False)
    parent_name = Column(String, nullable=True)  # channel parent name if thread
    author_display_name = Column(String, nullable=False)
    # content
    content = Column(String, nullable=True)
    clean_content = Column(String, nullable=True)
    embeds_json = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)


# ==== dalle ====
class DalleImage(Base):
    __tablename__ = "dalle_images"

    id = Column(Integer, primary_key=True)
    author_id = Column(BigInteger, nullable=False)
    model = Column(String, nullable=False)
    prompt = Column(String, nullable=False)
    size = Column(String, nullable=False)
    style = Column(String, nullable=False)

    data = Column(LargeBinary, nullable=False)
    filename = Column(String, nullable=False)
    revised_prompt = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
