from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('problems', '0001_initial'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('public_id', models.SlugField(unique=True)),
                ('allowed_instructors', models.ManyToManyField(blank=True, related_name='shared_quizzes', to='accounts.instructor')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='owned_quizzes', to='accounts.instructor')),
            ],
        ),
        migrations.CreateModel(
            name='QuizAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_identifier', models.CharField(max_length=255)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('extra_info', models.JSONField(blank=True, null=True)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='quizzes.quiz')),
            ],
        ),
        migrations.CreateModel(
            name='QuizSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=255)),
                ('order', models.IntegerField()),
                ('problem_bank', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='slots', to='problems.problembank')),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slots', to='quizzes.quiz')),
            ],
            options={'ordering': ['order']},
        ),
        migrations.CreateModel(
            name='QuizSlotProblemBank',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('problem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slot_links', to='problems.problem')),
                ('quiz_slot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slot_problems', to='quizzes.quizslot')),
            ],
        ),
        migrations.CreateModel(
            name='QuizAttemptSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answer_text', models.TextField(blank=True, null=True)),
                ('answered_at', models.DateTimeField(blank=True, null=True)),
                ('assigned_problem', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='problems.problem')),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempt_slots', to='quizzes.quizattempt')),
                ('slot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempt_slots', to='quizzes.quizslot')),
            ],
        ),
        migrations.AddConstraint(
            model_name='quizslotproblembank',
            constraint=models.UniqueConstraint(fields=('quiz_slot', 'problem'), name='unique_slot_problem_link'),
        ),
        migrations.AddConstraint(
            model_name='quizattemptslot',
            constraint=models.UniqueConstraint(fields=('attempt', 'slot'), name='unique_attempt_slot_entry'),
        ),
    ]
