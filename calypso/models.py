from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String
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
