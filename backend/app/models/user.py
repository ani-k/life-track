import uuid
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, GUID, new_uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=new_uuid
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # TODO(auth): restore relationship once Space.user_id FK is re-added:
    # spaces: Mapped[list["Space"]] = relationship(
    #     "Space", back_populates="owner", cascade="all, delete-orphan"
    # )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
