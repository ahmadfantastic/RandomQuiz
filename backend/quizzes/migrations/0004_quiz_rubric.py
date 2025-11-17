from django.db import migrations, models
import django.db.models.deletion


def _load_default_rubric():
    try:
        from quizzes.response_config import load_response_config
        return load_response_config()
    except FileNotFoundError:
        return {'scale': [], 'criteria': []}


def normalize_scale(config):
    entries = []
    for index, option in enumerate(config.get('scale') or []):
        value = option.get('value')
        label = option.get('label')
        if value is None or label is None:
            continue
        entries.append({'order': index, 'value': value, 'label': label})
    return entries


def normalize_criteria(config):
    entries = []
    for index, criterion in enumerate(config.get('criteria') or []):
        criterion_id = str(criterion.get('id') or '').strip()
        name = criterion.get('name')
        description = criterion.get('description')
        if not criterion_id or name is None or description is None:
            continue
        entries.append(
            {
                'order': index,
                'criterion_id': criterion_id,
                'name': name,
                'description': description,
            }
        )
    return entries


def populate_existing_quizzes(apps, schema_editor):
    Quiz = apps.get_model('quizzes', 'Quiz')
    Scale = apps.get_model('quizzes', 'QuizRatingScaleOption')
    Criterion = apps.get_model('quizzes', 'QuizRatingCriterion')
    config = _load_default_rubric()
    scale_entries = normalize_scale(config)
    criteria_entries = normalize_criteria(config)
    if not scale_entries or not criteria_entries:
        return
    for quiz in Quiz.objects.all():
        if Scale.objects.filter(quiz=quiz).exists() or Criterion.objects.filter(quiz=quiz).exists():
            continue
        scale_objs = [Scale(quiz=quiz, order=entry['order'], value=entry['value'], label=entry['label']) for entry in scale_entries]
        Scale.objects.bulk_create(scale_objs)
        criterion_objs = [
            Criterion(
                quiz=quiz,
                order=entry['order'],
                criterion_id=entry['criterion_id'],
                name=entry['name'],
                description=entry['description'],
            )
            for entry in criteria_entries
        ]
        Criterion.objects.bulk_create(criterion_objs)


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0003_quizattemptinteraction'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuizRatingScaleOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField()),
                ('value', models.IntegerField()),
                ('label', models.CharField(max_length=255)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rating_scale_options', to='quizzes.quiz')),
            ],
            options={
                'ordering': ['order'],
                'constraints': [models.UniqueConstraint(fields=['quiz', 'value'], name='unique_quiz_scale_value')],
            },
        ),
        migrations.CreateModel(
            name='QuizRatingCriterion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField()),
                ('criterion_id', models.CharField(max_length=32)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rating_criteria', to='quizzes.quiz')),
            ],
            options={
                'ordering': ['order'],
                'constraints': [models.UniqueConstraint(fields=['quiz', 'criterion_id'], name='unique_quiz_criterion_id')],
            },
        ),
        migrations.RunPython(populate_existing_quizzes, migrations.RunPython.noop),
    ]
