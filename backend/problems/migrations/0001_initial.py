from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProblemBank',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='problem_banks', to='accounts.instructor')),
            ],
        ),
        migrations.CreateModel(
            name='Problem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_in_bank', models.IntegerField()),
                ('statement', models.TextField()),
                ('problem_bank', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='problems', to='problems.problembank')),
            ],
            options={'ordering': ['order_in_bank']},
        ),
        migrations.AddConstraint(
            model_name='problem',
            constraint=models.UniqueConstraint(fields=('problem_bank', 'order_in_bank'), name='unique_problem_order_in_bank'),
        ),
    ]
