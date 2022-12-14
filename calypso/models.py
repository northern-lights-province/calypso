import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
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

    contributions = relationship("CommunityGoalContribution", back_populates="goal")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "cost_cp": self.cost_cp,
            "funded_cp": self.funded_cp,
            "message_id": self.message_id,
            "description": self.description,
            "image_url": self.image_url,
        }


class CommunityGoalContribution(Base):
    __tablename__ = "cg_contributions"

    id = Column(Integer, primary_key=True)
    goal_id = Column(Integer, ForeignKey("cg_goals.id", ondelete="CASCADE"))
    user_id = Column(BigInteger, nullable=False)
    amount_cp = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    goal = relationship("CommunityGoal", back_populates="contributions")
