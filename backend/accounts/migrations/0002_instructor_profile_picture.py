from django.db import migrations, models

import accounts.models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='instructor',
            name='profile_picture',
            field=models.ImageField(blank=True, null=True, upload_to=accounts.models.instructor_profile_picture_upload_to),
        ),
    ]
