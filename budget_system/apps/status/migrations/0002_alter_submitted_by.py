# Fix bsa_submission_status: rename submitted_by_id to submitted_by (text), drop submitted_at

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('status', '0001_initial'),
    ]

    operations = [
        # Drop the old FK column (submitted_by_id) created by the ForeignKey field
        migrations.RunSQL(
            sql='ALTER TABLE bsa_submission_status DROP COLUMN IF EXISTS submitted_by_id;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Drop submitted_at
        migrations.RunSQL(
            sql='ALTER TABLE bsa_submission_status DROP COLUMN IF EXISTS submitted_at;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Add submitted_by as a text column
        migrations.RunSQL(
            sql='ALTER TABLE bsa_submission_status ADD COLUMN submitted_by TEXT NULL;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Tell Django the model state is now correct
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='budgetsubmissionstatus',
                    name='submitted_by',
                ),
                migrations.AddField(
                    model_name='budgetsubmissionstatus',
                    name='submitted_by',
                    field=models.TextField(blank=True, null=True),
                ),
                migrations.RemoveField(
                    model_name='budgetsubmissionstatus',
                    name='submitted_at',
                ),
            ],
            database_operations=[],
        ),
    ]
