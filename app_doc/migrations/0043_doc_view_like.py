# 文档浏览次数与点赞功能

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app_doc', '0042_project_index_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='doc',
            name='view_count',
            field=models.PositiveIntegerField(default=0, verbose_name='浏览次数'),
        ),
        migrations.AddField(
            model_name='doc',
            name='like_count',
            field=models.PositiveIntegerField(default=0, verbose_name='点赞数'),
        ),
        migrations.CreateModel(
            name='DocLike',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visitor_key', models.CharField(max_length=64, verbose_name='访客标识')),
                ('create_time', models.DateTimeField(auto_now_add=True)),
                ('doc', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app_doc.doc')),
            ],
            options={
                'verbose_name': '文档点赞',
                'verbose_name_plural': '文档点赞',
                'unique_together': {('doc', 'visitor_key')},
            },
        ),
    ]
