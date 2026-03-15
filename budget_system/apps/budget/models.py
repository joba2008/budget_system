"""Budget models — SQLAlchemy ORM."""
from sqlalchemy import (
    Column, Integer, String, Numeric, ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from config.database import Base, get_db


def get_all_versions():
    """Get all distinct version names from bsa_main, sorted."""
    with get_db() as session:
        rows = session.query(BsaMain.version).distinct().order_by(BsaMain.version).all()
        return [r[0] for r in rows]


def parse_version_name(version_name):
    """
    Parse version string like 'fy26-B1' into fiscal_year and scenario.
    Returns (fiscal_year, scenario) tuple.
    """
    parts = version_name.split('-', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return version_name, ''


class BsaMain(Base):
    __tablename__ = 'bsa_main'

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), index=True)
    data_type = Column(String(50), default='')
    under_ops_control = Column(String(10), default='')
    ccgl = Column(String(50), default='')
    glc = Column(String(50), default='')
    cc = Column(String(50), default='')
    non_controllable = Column(String(50), default='')
    area = Column(String(50), index=True)
    dept = Column(String(50), index=True)
    dept_group = Column(String(50), index=True)
    dept_ppt = Column(String(300), default='')
    category = Column(String(100), index=True)
    discretionary = Column(String(50), default='')
    at_var = Column(Numeric(18, 4), nullable=True)
    self_study_var = Column(Numeric(18, 4), nullable=True)
    spends_control = Column(String(10), default='')
    iecs_view = Column(String(10), default='')
    levels = Column(String(300), default='')
    accounts = Column(String(300), default='')
    budgeter = Column(String(100), index=True)
    baseline_adjustment = Column(Numeric(18, 2), nullable=True)

    # Relationships
    volume_actuals = relationship('BsaVolumeActual', back_populates='main', cascade='all, delete-orphan')
    volumes = relationship('BsaVolume', back_populates='main', cascade='all, delete-orphan')
    actuals = relationship('BsaActual', back_populates='main', cascade='all, delete-orphan')
    spendings = relationship('BsaSpending', back_populates='main', cascade='all, delete-orphan')
    rebase_financeviews = relationship('BsaRebaseFinanceview', back_populates='main', cascade='all, delete-orphan')
    rebase_opsviews = relationship('BsaRebaseOpsview', back_populates='main', cascade='all, delete-orphan')
    savings = relationship('BsaSaving', back_populates='main', cascade='all, delete-orphan')
    newadds = relationship('BsaNewadd', back_populates='main', cascade='all, delete-orphan')
    newadd_approveds = relationship('BsaNewaddApproved', back_populates='main', cascade='all, delete-orphan')
    final_budgets = relationship('BsaFinalBudget', back_populates='main', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_bsa_main_version_dept', 'version', 'dept'),
        Index('ix_bsa_main_version_budgeter', 'version', 'budgeter'),
    )

    def __repr__(self):
        return f'<BsaMain {self.version} | {self.cc}-{self.glc} | {self.accounts}>'


class BsaVolumeActual(Base):
    __tablename__ = 'bsa_volume_actual'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='volume_actuals')

    __table_args__ = (
        UniqueConstraint('main_id', 'period', name='uq_volume_actual_main_period'),
    )


class BsaVolume(Base):
    __tablename__ = 'bsa_volume'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    scenario = Column(String(10), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='volumes')

    __table_args__ = (
        UniqueConstraint('main_id', 'scenario', 'period', name='uq_volume_main_scenario_period'),
    )


class BsaActual(Base):
    __tablename__ = 'bsa_actual'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='actuals')

    __table_args__ = (
        UniqueConstraint('main_id', 'period', name='uq_actual_main_period'),
    )


class BsaSpending(Base):
    __tablename__ = 'bsa_spending'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='spendings')

    __table_args__ = (
        UniqueConstraint('main_id', 'period', name='uq_spending_main_period'),
    )


class BsaRebaseFinanceview(Base):
    __tablename__ = 'bsa_rebase_financeview'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='rebase_financeviews')

    __table_args__ = (
        UniqueConstraint('main_id', 'period', name='uq_rebase_fv_main_period'),
    )


class BsaRebaseOpsview(Base):
    __tablename__ = 'bsa_rebase_opsview'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='rebase_opsviews')

    __table_args__ = (
        UniqueConstraint('main_id', 'period', name='uq_rebase_ov_main_period'),
    )


class BsaSaving(Base):
    __tablename__ = 'bsa_saving'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='savings')

    __table_args__ = (
        UniqueConstraint('main_id', 'period', name='uq_saving_main_period'),
    )


class BsaNewadd(Base):
    __tablename__ = 'bsa_newadd'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='newadds')

    __table_args__ = (
        UniqueConstraint('main_id', 'period', name='uq_newadd_main_period'),
    )


class BsaFinalBudget(Base):
    __tablename__ = 'bsa_final_budget'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='final_budgets')

    __table_args__ = (
        UniqueConstraint('main_id', 'period', name='uq_final_budget_main_period'),
    )


class BsaNewaddApproved(Base):
    __tablename__ = 'bsa_newadd_approved'

    id = Column(Integer, primary_key=True, autoincrement=True)
    main_id = Column(Integer, ForeignKey('bsa_main.id', ondelete='CASCADE'), nullable=False)
    period = Column(String(20), nullable=False)
    value = Column(Numeric(18, 2), nullable=True)

    main = relationship('BsaMain', back_populates='newadd_approveds')

    __table_args__ = (
        UniqueConstraint('main_id', 'period', name='uq_newadd_approved_main_period'),
    )
