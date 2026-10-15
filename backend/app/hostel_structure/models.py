import enum

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import IdMixin, TimestampMixin
from app.extensions import db


class LocationKind(str, enum.Enum):
    FLOOR_WING = "FLOOR_WING"
    GROUND_FACILITY = "GROUND_FACILITY"


class Hostel(IdMixin, TimestampMixin, db.Model):
    __tablename__ = "hostels"

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    floors: Mapped[list["Floor"]] = relationship(
        back_populates="hostel", order_by="Floor.number", cascade="all, delete-orphan"
    )


class Floor(IdMixin, db.Model):
    __tablename__ = "floors"
    __table_args__ = (UniqueConstraint("hostel_id", "number"),)

    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"), nullable=False)
    number: Mapped[int] = mapped_column(nullable=False)

    hostel: Mapped[Hostel] = relationship(back_populates="floors")
    wings: Mapped[list["Wing"]] = relationship(
        back_populates="floor", order_by="Wing.code", cascade="all, delete-orphan"
    )

    @property
    def label(self) -> str:
        return "Ground floor" if self.number == 0 else f"Floor {self.number}"


class Wing(IdMixin, db.Model):
    __tablename__ = "wings"
    __table_args__ = (UniqueConstraint("floor_id", "code"),)

    floor_id: Mapped[int] = mapped_column(ForeignKey("floors.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(4), nullable=False)

    floor: Mapped[Floor] = relationship(back_populates="wings")
    rooms: Mapped[list["Room"]] = relationship(
        back_populates="wing", order_by="Room.number", cascade="all, delete-orphan"
    )


class Room(IdMixin, db.Model):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("wing_id", "number"),)

    wing_id: Mapped[int] = mapped_column(ForeignKey("wings.id"), nullable=False)
    number: Mapped[str] = mapped_column(String(16), nullable=False)

    wing: Mapped[Wing] = relationship(back_populates="rooms")


class Location(IdMixin, db.Model):
    __tablename__ = "locations"

    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"), nullable=False)
    kind: Mapped[LocationKind] = mapped_column(
        Enum(LocationKind, name="location_kind"), nullable=False
    )
    floor_id: Mapped[int] = mapped_column(ForeignKey("floors.id"), nullable=False)
    wing_id: Mapped[int | None] = mapped_column(ForeignKey("wings.id"))
    facility_name: Mapped[str | None] = mapped_column(String(80))

    hostel: Mapped[Hostel] = relationship()
    floor: Mapped[Floor] = relationship()
    wing: Mapped[Wing | None] = relationship()

    @property
    def label(self) -> str:
        if self.kind == LocationKind.GROUND_FACILITY:
            return f"{self.floor.label}, {self.facility_name}"
        return f"{self.floor.label}, Wing {self.wing.code}"
