"""User permission model — SQLAlchemy ORM."""
from sqlalchemy import Column, Integer, String, UniqueConstraint, JSON

from config.database import Base


class BsaPermission(Base):
    """User permission table - validates system access and role on login."""
    __tablename__ = 'bsa_permission'

    ROLE_CHOICES = [
        ('admin', 'System Admin'),
        ('budgeter', 'Budgeter'),
        ('viewer', 'Viewer'),
    ]
    ROLE_PRIORITY = {'admin': 3, 'budgeter': 2, 'viewer': 1}

    AREA_CHOICES = [
        ('Automation', 'Automation'),
        ('EHS', 'EHS'),
        ('Facility', 'Facility'),
        ('FG&WH&Site logistics', 'FG&WH&Site logistics'),
        ('Assy MFG', 'Assy MFG'),
        ('TMO MFG', 'TMO MFG'),
        ('DMTE ENG', 'DMTE ENG'),
        ('MPTE ENG', 'MPTE ENG'),
        ('Assy ENG', 'Assy ENG'),
        ('QA', 'QA'),
        ('PMO', 'PMO'),
        ('Planning', 'Planning'),
    ]

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_mail = Column(String(320), nullable=False)
    user_role = Column(String(50), nullable=False)
    user_area = Column(JSON, default=list)

    __table_args__ = (
        UniqueConstraint('user_mail', 'user_role', name='uq_permission_mail_role'),
    )

    def __repr__(self):
        return f'<BsaPermission {self.user_mail} - {self.user_role} - {self.user_area}>'

    @classmethod
    def get_highest_role(cls, session, username):
        """Get the highest priority role for a user."""
        perms = session.query(cls).filter(cls.user_mail == username).all()
        if not perms:
            return None
        return max(perms, key=lambda p: cls.ROLE_PRIORITY.get(p.user_role, 0)).user_role
