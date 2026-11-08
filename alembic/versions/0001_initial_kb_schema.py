"""Initial Knowledge Base schema with pgvector and NOT NULL source_id constraints

Revision ID: 0001_initial_kb_schema
Revises: 
Create Date: 2026-09-21 19:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001_initial_kb_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension for multilingual commodity alias matching
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. sources table (backbone citation registry)
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("citation", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("doi", sa.String(length=128), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. commodities table
    op.create_table(
        "commodities",
        sa.Column("commodity_id", sa.String(length=128), nullable=False),
        sa.Column("names", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("group", sa.String(length=64), nullable=False),
        sa.Column("commodity_class", sa.String(length=64), nullable=False),
        sa.Column("moisture_pct", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("water_activity", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fat_pct", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ph", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("respiration_model", sa.String(length=64), nullable=True),
        sa.Column("respiration_ea_kj_mol", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("respiration_ref_t_c", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("respiration_ref_rate", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("storage_optimum_t_c_min", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("storage_optimum_t_c_max", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("storage_optimum_rh_min", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("storage_optimum_rh_max", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("storage_life_days_min", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("storage_life_days_max", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("chilling_sensitive_below_c", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("ethylene_production", sa.String(length=64), nullable=True),
        sa.Column("ethylene_sensitivity", sa.String(length=64), nullable=True),
        sa.Column(
            "failure_modes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "light_sensitive",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("light_note", sa.Text(), nullable=True),
        sa.Column(
            "state_modifiers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("commodity_id"),
    )

    # 4. commodity_aliases table (with pgvector)
    op.create_table(
        "commodity_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("commodity_id", sa.String(length=128), nullable=False),
        sa.Column("alias", sa.String(length=128), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.commodity_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_commodity_aliases_alias"), "commodity_aliases", ["alias"], unique=False)
    op.create_index(op.f("ix_commodity_aliases_commodity_id"), "commodity_aliases", ["commodity_id"], unique=False)

    # 5. films table
    op.create_table(
        "films",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("film_name", sa.String(length=128), nullable=False),
        sa.Column("thickness_um", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("otr_value", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("otr_min", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("otr_max", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("otr_test_temperature_c", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("otr_test_rh_pct", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("otr_test_method", sa.String(length=64), nullable=False),
        sa.Column("wvtr_value", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("wvtr_min", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("wvtr_max", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("wvtr_test_temperature_c", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("wvtr_test_rh_pct", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("wvtr_test_method", sa.String(length=64), nullable=False),
        sa.Column("barrier_class", sa.String(length=64), nullable=False),
        sa.Column("typical_use", sa.Text(), nullable=False),
        sa.Column("epr_category", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. structures table
    op.create_table(
        "structures",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("layer_stack", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("gauge_per_layer_um", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("composite_thickness_um", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("measured_otr", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("measured_wvtr", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("otr_test_conditions", sa.String(length=128), nullable=False),
        sa.Column("wvtr_test_conditions", sa.String(length=128), nullable=False),
        sa.Column("cost_inr_per_sqm", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("indicative_cost_per_pack", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("epr_category", sa.String(length=32), nullable=False),
        sa.Column("recyclability_notes", sa.Text(), nullable=True),
        sa.Column("typical_applications", sa.Text(), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 7. isotherms table
    op.create_table(
        "isotherms",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("food_class_or_commodity", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=32), nullable=False),
        sa.Column("temperature_c", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("m0", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("c_g", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("k", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("linear_slope_b", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("linear_intercept_c", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("aw_min", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("aw_max", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("aw_crit", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 8. map_targets table
    op.create_table(
        "map_targets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("product_group", sa.String(length=128), nullable=False),
        sa.Column("target_o2_min", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("target_o2_max", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("target_co2_min", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("target_co2_max", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("o2_floor", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("co2_injury_ceiling", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("balance_gas", sa.String(length=32), server_default="N2", nullable=False),
        sa.Column("optimum_temp_c_min", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("optimum_temp_c_max", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 9. state_modifiers table
    op.create_table(
        "state_modifiers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("modifier_name", sa.String(length=64), nullable=False),
        sa.Column("commodity_group", sa.String(length=64), nullable=False),
        sa.Column("respiration_factor_min", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("respiration_factor_max", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("ethylene_factor_min", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("ethylene_factor_max", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("aw_delta", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("microbial_risk_level", sa.String(length=32), nullable=True),
        sa.Column("new_failure_mode", sa.String(length=64), nullable=True),
        sa.Column("max_ambient_hours", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("life_factor_min", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("life_factor_max", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column(
            "requires_antifog",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("state_modifiers")
    op.drop_table("map_targets")
    op.drop_table("isotherms")
    op.drop_table("structures")
    op.drop_table("films")
    op.drop_index(op.f("ix_commodity_aliases_commodity_id"), table_name="commodity_aliases")
    op.drop_index(op.f("ix_commodity_aliases_alias"), table_name="commodity_aliases")
    op.drop_table("commodity_aliases")
    op.drop_table("commodities")
    op.drop_table("sources")
    op.execute("DROP EXTENSION IF EXISTS vector;")
