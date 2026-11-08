"""
SQLAlchemy ORM models for Aavaran Knowledge Base.

Enforces:
- PostgreSQL 16 relational tables with JSONB and pgvector(384) support
- NOT NULL foreign key constraint source_id referencing sources(id) on every data table
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Source(Base):
    __tablename__ = "sources"

    id = Column(String(64), primary_key=True)
    source_type = Column(String(32), nullable=False)
    name = Column(String(255), nullable=False)
    citation = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    doi = Column(String(128), nullable=True)
    publication_year = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    commodities = relationship("Commodity", back_populates="source")
    commodity_aliases = relationship("CommodityAlias", back_populates="source")
    films = relationship("Film", back_populates="source")
    structures = relationship("Structure", back_populates="source")
    isotherms = relationship("Isotherm", back_populates="source")
    map_targets = relationship("MapTarget", back_populates="source")
    state_modifiers = relationship("StateModifier", back_populates="source")


class Commodity(Base):
    __tablename__ = "commodities"

    commodity_id = Column(String(128), primary_key=True)
    names = Column(JSONB, nullable=False)
    group = Column(String(64), nullable=False)
    commodity_class = Column(String(64), nullable=False)
    
    moisture_pct = Column(JSONB, nullable=True)
    water_activity = Column(JSONB, nullable=True)
    fat_pct = Column(JSONB, nullable=True)
    ph = Column(JSONB, nullable=True)
    
    respiration_model = Column(String(64), nullable=True)
    respiration_ea_kj_mol = Column(JSONB, nullable=True)
    respiration_ref_t_c = Column(JSONB, nullable=True)
    respiration_ref_rate = Column(JSONB, nullable=True)
    
    storage_optimum_t_c_min = Column(Numeric(6, 2), nullable=True)
    storage_optimum_t_c_max = Column(Numeric(6, 2), nullable=True)
    storage_optimum_rh_min = Column(Numeric(6, 2), nullable=True)
    storage_optimum_rh_max = Column(Numeric(6, 2), nullable=True)
    storage_life_days_min = Column(Numeric(8, 2), nullable=True)
    storage_life_days_max = Column(Numeric(8, 2), nullable=True)
    chilling_sensitive_below_c = Column(Numeric(6, 2), nullable=True)
    
    ethylene_production = Column(String(64), nullable=True)
    ethylene_sensitivity = Column(String(64), nullable=True)
    
    failure_modes = Column(JSONB, nullable=False, server_default="[]")
    light_sensitive = Column(Boolean, nullable=False, default=False)
    light_note = Column(Text, nullable=True)
    state_modifiers = Column(JSONB, nullable=False, server_default="{}")
    
    source_id = Column(String(64), ForeignKey("sources.id"), nullable=False)
    source = relationship("Source", back_populates="commodities")
    aliases = relationship("CommodityAlias", back_populates="commodity", cascade="all, delete-orphan")


class CommodityAlias(Base):
    __tablename__ = "commodity_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    commodity_id = Column(String(128), ForeignKey("commodities.commodity_id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(128), nullable=False, index=True)
    language = Column(String(16), nullable=False)
    embedding = Column(Vector(384), nullable=True)
    source_id = Column(String(64), ForeignKey("sources.id"), nullable=False)

    commodity = relationship("Commodity", back_populates="aliases")
    source = relationship("Source", back_populates="commodity_aliases")


class Film(Base):
    __tablename__ = "films"

    id = Column(String(64), primary_key=True)
    film_name = Column(String(128), nullable=False)
    thickness_um = Column(Numeric(8, 2), nullable=False)
    
    otr_value = Column(Numeric(12, 4), nullable=False)
    otr_min = Column(Numeric(12, 4), nullable=True)
    otr_max = Column(Numeric(12, 4), nullable=True)
    otr_test_temperature_c = Column(Numeric(6, 2), nullable=False)
    otr_test_rh_pct = Column(Numeric(6, 2), nullable=False)
    otr_test_method = Column(String(64), nullable=False)
    
    wvtr_value = Column(Numeric(12, 4), nullable=False)
    wvtr_min = Column(Numeric(12, 4), nullable=True)
    wvtr_max = Column(Numeric(12, 4), nullable=True)
    wvtr_test_temperature_c = Column(Numeric(6, 2), nullable=False)
    wvtr_test_rh_pct = Column(Numeric(6, 2), nullable=False)
    wvtr_test_method = Column(String(64), nullable=False)
    
    barrier_class = Column(String(64), nullable=False)
    typical_use = Column(Text, nullable=False)
    epr_category = Column(String(32), nullable=False)
    
    source_id = Column(String(64), ForeignKey("sources.id"), nullable=False)
    source = relationship("Source", back_populates="films")


class Structure(Base):
    __tablename__ = "structures"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    layer_stack = Column(JSONB, nullable=False)
    gauge_per_layer_um = Column(JSONB, nullable=False)
    composite_thickness_um = Column(Numeric(8, 2), nullable=False)
    
    measured_otr = Column(Numeric(12, 4), nullable=False)
    measured_wvtr = Column(Numeric(12, 4), nullable=False)
    otr_test_conditions = Column(String(128), nullable=False)
    wvtr_test_conditions = Column(String(128), nullable=False)
    
    cost_inr_per_sqm = Column(Numeric(10, 2), nullable=False)
    indicative_cost_per_pack = Column(Numeric(10, 2), nullable=True)
    epr_category = Column(String(32), nullable=False)
    recyclability_notes = Column(Text, nullable=True)
    typical_applications = Column(Text, nullable=True)
    
    source_id = Column(String(64), ForeignKey("sources.id"), nullable=False)
    source = relationship("Source", back_populates="structures")


class Isotherm(Base):
    __tablename__ = "isotherms"

    id = Column(String(64), primary_key=True)
    food_class_or_commodity = Column(String(128), nullable=False)
    model_type = Column(String(32), nullable=False)
    temperature_c = Column(Numeric(6, 2), nullable=False)
    
    m0 = Column(Numeric(8, 4), nullable=True)
    c_g = Column(Numeric(8, 4), nullable=True)
    k = Column(Numeric(8, 4), nullable=True)
    linear_slope_b = Column(Numeric(8, 4), nullable=True)
    linear_intercept_c = Column(Numeric(8, 4), nullable=True)
    
    aw_min = Column(Numeric(6, 4), nullable=True)
    aw_max = Column(Numeric(6, 4), nullable=True)
    aw_crit = Column(Numeric(6, 4), nullable=True)
    
    source_id = Column(String(64), ForeignKey("sources.id"), nullable=False)
    source = relationship("Source", back_populates="isotherms")


class MapTarget(Base):
    __tablename__ = "map_targets"

    id = Column(String(64), primary_key=True)
    product_group = Column(String(128), nullable=False)
    target_o2_min = Column(Numeric(6, 2), nullable=False)
    target_o2_max = Column(Numeric(6, 2), nullable=False)
    target_co2_min = Column(Numeric(6, 2), nullable=False)
    target_co2_max = Column(Numeric(6, 2), nullable=False)
    o2_floor = Column(Numeric(6, 2), nullable=False)
    co2_injury_ceiling = Column(Numeric(6, 2), nullable=False)
    balance_gas = Column(String(32), nullable=False, default="N2")
    optimum_temp_c_min = Column(Numeric(6, 2), nullable=True)
    optimum_temp_c_max = Column(Numeric(6, 2), nullable=True)
    notes = Column(Text, nullable=True)
    
    source_id = Column(String(64), ForeignKey("sources.id"), nullable=False)
    source = relationship("Source", back_populates="map_targets")


class StateModifier(Base):
    __tablename__ = "state_modifiers"

    id = Column(String(64), primary_key=True)
    modifier_name = Column(String(64), nullable=False)
    commodity_group = Column(String(64), nullable=False)
    
    respiration_factor_min = Column(Numeric(6, 2), nullable=True)
    respiration_factor_max = Column(Numeric(6, 2), nullable=True)
    ethylene_factor_min = Column(Numeric(6, 2), nullable=True)
    ethylene_factor_max = Column(Numeric(6, 2), nullable=True)
    aw_delta = Column(Numeric(6, 4), nullable=True)
    microbial_risk_level = Column(String(32), nullable=True)
    new_failure_mode = Column(String(64), nullable=True)
    max_ambient_hours = Column(Numeric(8, 2), nullable=True)
    life_factor_min = Column(Numeric(6, 2), nullable=True)
    life_factor_max = Column(Numeric(6, 2), nullable=True)
    requires_antifog = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
    
    source_id = Column(String(64), ForeignKey("sources.id"), nullable=False)
    source = relationship("Source", back_populates="state_modifiers")


class BatchRecordDB(Base):
    """Append-only batch records table with SHA-256 hash chaining."""
    __tablename__ = "batch_records"

    batch_code = Column(String(64), primary_key=True)
    commodity = Column(String(128), nullable=False)
    quantity = Column(String(64), nullable=False)
    harvest_or_production_date = Column(DateTime(timezone=True), nullable=False)
    packaging_used = Column(String(255), nullable=False)
    result_id = Column(String(64), nullable=False, index=True)
    packer_identity = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    handling_events = Column(JSONB, nullable=False, server_default="[]")
    prev_hash = Column(String(64), nullable=False)
    sha256_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default="{}")

