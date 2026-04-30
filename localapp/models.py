from djongo import models
from bson import ObjectId


def generate_object_id():
    return str(ObjectId())


class SuiteTag(models.Model):
    id = models.CharField(primary_key=True, default=generate_object_id, editable=False, max_length=24)
    name = models.CharField(max_length=255, null=False, blank=False, verbose_name="Tag Name",unique=True)

    def __str__(self):
        return self.name.upper()
    class Meta:
        db_table = "localapp_suitetag"


class TagMapping(models.Model):
    # tag_name = models.EmbeddedField(model_container=SuiteTag)
    tag_name = models.ForeignKey(SuiteTag, on_delete=models.CASCADE, verbose_name="Tag Name",db_column='tag_name_id')
    train_name = models.CharField(max_length=255, null=False, blank=False, verbose_name="Train Name")
    suite_name = models.CharField(max_length=255, null=False, blank=False, verbose_name="Suite Name")
    def __str__(self):
        return self.tag_name.name

# Create your models here.
