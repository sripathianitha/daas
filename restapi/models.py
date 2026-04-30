from django.db import models
from django.utils import timezone

ERROR_CATEGORY_CHOICES = (
    ('QA', 'QA'),
    ('INFRA', 'INFRA'),
)

COHESITY_OS_CHOICES = (
    ('cohesity', 'Cohesity'),
    ('hecp', 'HECP'),
    ('hedp', 'HEDP'),
    ('onprem', 'OnPrem'),
)

SEVERE_ERR_TYPE = (
    ('buggy','Buggy'),
    ('expected','Expected'),
    ('need_analysis', 'Need Analysis'),
    ('new_error','New Error')
)
# Create your models here.
class Trainlogdata(models.Model):
    area = models.CharField(max_length=255)
    trainname = models.CharField(max_length=255)
    date = models.CharField(max_length=255)
    logurl = models.TextField()
    build = models.CharField(max_length=255)

    def __str__(self):
        return self.trainname + "-" + self.build

    class Meta:
        ordering = ['trainname', 'date']


class AllBranch(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class ErrorSignature(models.Model):
    signature = models.CharField(max_length=255, null=False, blank=False, unique=True,verbose_name="Error Message Signature")
    readable_sig = models.CharField(max_length=255, null=False, blank=False, verbose_name="Readable Error Message")
    common_solution = models.TextField(verbose_name="Common Solutions",null=True, blank=True)
    common_solution_flag = models.BooleanField(default=False, null=False, blank=False,
                                               verbose_name="Given Common Solution Applicable to this Error sig")
    def __str__(self):
        return self.readable_sig

    class Meta:
        ordering = ['readable_sig']

class OptimalSolution(models.Model):
    cleaned_error_msg = models.TextField(null=False, blank=False, unique=True, verbose_name="Cleaned Error Message")
    optimal_solution = models.TextField(verbose_name="Optimal Solutions",null=True, blank=True)
    err_signature = models.ForeignKey(ErrorSignature,on_delete=models.CASCADE,default=1)
    updated_date = models.DateTimeField(default=timezone.now, verbose_name="Updated Date")
    err_category = models.CharField(null=False,blank=False,default="QA",verbose_name="Error Category",max_length=10,
                                    choices=ERROR_CATEGORY_CHOICES)
    email_address = models.EmailField(max_length=254,default="admin@cohesity.com",null=False,blank=False)

    def __str__(self):
        return self.err_signature.readable_sig

    class Meta:
        ordering = ['err_signature__readable_sig']

class SquadDetails(models.Model):
    os = models.CharField(max_length=255, null=False, blank=False, verbose_name="Cohesity OS Type",
                          choices=COHESITY_OS_CHOICES)
    branch = models.CharField(max_length=255, null=True, blank=True, verbose_name="Branch")
    area = models.CharField(max_length=255, null=True, blank=True, verbose_name="Area")
    train_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Train Name")
    suite_group = models.CharField(max_length=255, null=True, blank=True, verbose_name="Suite Group")
    suite_owner = models.CharField(max_length=255, null=True, blank=True, verbose_name="Suite Owner")
    suite_squad = models.CharField(max_length=255, null=True, blank=True, verbose_name="Suite Squad")
    suite_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Suite name")

    def __str__(self):
        return self.train_name + "-" + self.suite_name + "-" + self.suite_squad

class SevereDetail(models.Model):
    error_message = models.TextField(null=True, blank=False, verbose_name="Severe Error Message")
    cleaned_error = models.CharField(max_length=255, null=False, blank=False, verbose_name="Error Message Keywords")
    error_category = models.CharField(max_length=255, null=False, blank=False, verbose_name="Error Type",
                          choices=SEVERE_ERR_TYPE, default='new_error')
    bug_id = models.CharField(max_length=255, null=True, blank=True, verbose_name="Bug ID")
    comments = models.CharField(max_length=255, null=True, blank=True, verbose_name="Comments")