"""Initial migration - create all tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums first
    lot_status_enum = sa.Enum(
        'UNASSIGNED', 'LEASED', 'IN_TRANSIT', 'DELIVERED', 
        'EXPIRED', 'DISCARDED', 'ABORTED_UNSAFE',
        name='lot_status_enum'
    )
    lot_status_enum.create(op.get_bind(), checkfirst=True)
    
    lease_state_enum = sa.Enum(
        'OFFERED', 'ACCEPTED', 'ARRIVED_DONOR', 'PICKED_UP',
        'NEAR_SHELTER', 'DELIVERED', 'EXPIRED', 'RELEASED',
        'REROUTED', 'ABORTED_UNSAFE',
        name='lease_state_enum'
    )
    lease_state_enum.create(op.get_bind(), checkfirst=True)
    
    event_type_enum = sa.Enum(
        'BATCH_CREATED', 'BATCH_REVISED', 'LOT_CREATED', 'LEASE_OFFERED',
        'LEASE_ACCEPTED', 'LEASE_DECLINED', 'RIDER_PING', 'RIDER_MILESTONE',
        'LEASE_STALLED', 'LEASE_EXPIRED', 'LEASE_RELEASED', 'PICKUP_CONFIRMED',
        'DELIVERY_CONFIRMED', 'DEMAND_CHANGED', 'SHELTER_CLOSED',
        'WALK_IN_RECEIVED', 'CAPABILITY_CHANGED', 'REROUTE_PROPOSED',
        'REROUTE_ACKED', 'UNSAFE_REPORTED', 'LOT_EXPIRED', 'LOT_DISCARDED',
        'PLAN_COMMITTED', 'CHAOS_INJECTED',
        name='event_type_enum'
    )
    event_type_enum.create(op.get_bind(), checkfirst=True)

    # donors table
    op.create_table(
        'donors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('contact', sa.String(255)),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # riders table
    op.create_table(
        'riders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50)),
        sa.Column('vehicle_capacity', sa.Integer(), default=50),
        sa.Column('insulated_box', sa.Boolean(), default=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('status', sa.String(50), default='AVAILABLE'),
        sa.Column('reliability_alpha', sa.Integer(), default=1),
        sa.Column('reliability_beta', sa.Integer(), default=1),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # shelters table
    op.create_table(
        'shelters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('contact', sa.String(255)),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('need', sa.Integer(), default=0),
        sa.Column('received', sa.Integer(), default=0),
        sa.Column('committed', sa.Integer(), default=0),
        sa.Column('intake_open', sa.Boolean(), default=True),
        sa.Column('accepts_diet_tags', postgresql.JSON(astext_type=sa.Text()), default=list),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # shelter_capabilities table
    op.create_table(
        'shelter_capabilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shelter_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('value', sa.Boolean(), default=True),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['shelter_id'], ['shelters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('shelter_id', 'name', name='uq_shelter_capability')
    )

    # overflow_sinks table
    op.create_table(
        'overflow_sinks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('open_from', sa.String(5)),
        sa.Column('open_to', sa.String(5)),
        sa.Column('intake_limit', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # batches table
    op.create_table(
        'batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('donor_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('qty_portions', sa.Integer(), nullable=False),
        sa.Column('cooked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('shelf_life_min', sa.Integer(), nullable=False),
        sa.Column('safe_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('pickup_window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('pickup_window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cold_chain', sa.Boolean(), default=False),
        sa.Column('allergens', postgresql.JSON(astext_type=sa.Text()), default=list),
        sa.Column('diet_tags', postgresql.JSON(astext_type=sa.Text()), default=list),
        sa.Column('status', sa.String(50), default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['donor_id'], ['donors.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # lots table
    op.create_table(
        'lots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False),
        sa.Column('status', lot_status_enum, default='UNASSIGNED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['batch_id'], ['batches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # leases table
    op.create_table(
        'leases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lot_id', sa.Integer(), nullable=False),
        sa.Column('rider_id', sa.Integer(), nullable=False),
        sa.Column('shelter_id', sa.Integer(), nullable=False),
        sa.Column('state', lease_state_enum, default='OFFERED', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_progress_at', sa.DateTime(timezone=True)),
        sa.Column('progress_pings', sa.Integer(), default=0),
        sa.Column('fallbacks', postgresql.JSON(astext_type=sa.Text()), default=list),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['lot_id'], ['lots.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rider_id'], ['riders.id']),
        sa.ForeignKeyConstraint(['shelter_id'], ['shelters.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # lease_stops table
    op.create_table(
        'lease_stops',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lease_id', sa.Integer(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('location_type', sa.String(50), nullable=False),
        sa.Column('location_id', sa.Integer(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('eta_p50', sa.Integer()),
        sa.Column('eta_p90', sa.Integer()),
        sa.Column('arrived_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['lease_id'], ['leases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # events table
    op.create_table(
        'events',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('type', event_type_enum, nullable=False),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('actor_type', sa.String(50)),
        sa.Column('actor_id', sa.Integer()),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key')
    )
    op.create_index('ix_events_created_at', 'events', ['created_at'])
    op.create_index('ix_events_actor', 'events', ['actor_type', 'actor_id'])

    # scheduled_actions table
    op.create_table(
        'scheduled_actions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('target_type', sa.String(50)),
        sa.Column('target_id', sa.Integer()),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), default={}),
        sa.Column('execute_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(50), default='PENDING'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scheduled_actions_execute_at', 'scheduled_actions', ['execute_at'])

    # notifications_outbox table
    op.create_table(
        'notifications_outbox',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('recipient', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(255)),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), default='PENDING'),
        sa.Column('attempts', sa.Integer(), default=0),
        sa.Column('sent_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # plans table
    op.create_table(
        'plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('assignments', postgresql.JSON(astext_type=sa.Text()), default=list),
        sa.Column('explanations', postgresql.JSON(astext_type=sa.Text()), default=list),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('committed_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id')
    )

    # metrics_snapshots table
    op.create_table(
        'metrics_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('portions_delivered', sa.Integer(), default=0),
        sa.Column('portions_wasted', sa.Integer(), default=0),
        sa.Column('portions_wasted_expired', sa.Integer(), default=0),
        sa.Column('portions_wasted_unsafe', sa.Integer(), default=0),
        sa.Column('portions_wasted_capacity', sa.Integer(), default=0),
        sa.Column('lease_violations', sa.Integer(), default=0),
        sa.Column('ghost_rate', sa.Float(), default=0.0),
        sa.Column('avg_reroute_time_ms', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('metrics_snapshots')
    op.drop_table('plans')
    op.drop_table('notifications_outbox')
    op.drop_table('scheduled_actions')
    op.drop_index('ix_events_actor', table_name='events')
    op.drop_index('ix_events_created_at', table_name='events')
    op.drop_table('events')
    op.drop_table('lease_stops')
    op.drop_table('leases')
    op.drop_table('lots')
    op.drop_table('batches')
    op.drop_table('overflow_sinks')
    op.drop_table('shelter_capabilities')
    op.drop_table('shelters')
    op.drop_table('riders')
    op.drop_table('donors')
    
    # Drop enums
    event_type_enum = sa.Enum(name='event_type_enum')
    event_type_enum.drop(op.get_bind(), checkfirst=True)
    
    lease_state_enum = sa.Enum(name='lease_state_enum')
    lease_state_enum.drop(op.get_bind(), checkfirst=True)
    
    lot_status_enum = sa.Enum(name='lot_status_enum')
    lot_status_enum.drop(op.get_bind(), checkfirst=True)