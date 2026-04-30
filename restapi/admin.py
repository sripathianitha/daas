from django.contrib import admin
from .models import *
from django import forms
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
import csv
from io import StringIO
# from .models import OptimalSolution, ErrorSignature
# from .forms import CsvImportForm
from django import forms
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TrainlogdataAdmin(admin.ModelAdmin):
    """ Team Role admin view with modifications """
    model = Trainlogdata
    ordering = ('-date','trainname')
    search_fields = ['trainname', 'build']
    list_display = ['date', 'trainname', 'build']
    readonly_fields = ('date','trainname','build','logurl','area',)

class AllBranchAdmin(admin.ModelAdmin):
    model = AllBranch
    ordering = ('name',)
    search_fields = ['name']
    list_display = ['name']
    readonly_fields = ('name',)

class SuiteDetailAdmin(admin.ModelAdmin):
    model = SquadDetails
    ordering = ('train_name',)
    search_fields = ['suite_name','train_name','suite_squad']
    list_display = ['train_name','suite_name','suite_squad']


class CsvImportForm(forms.Form):
    csv_upload = forms.FileField()


class ErrorSignatureAdmin(admin.ModelAdmin):
    model = ErrorSignature
    list_display = ['signature','readable_sig']
    search_fields = ['signature', 'readable_sig']

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [path('upload-csv/', self.upload_csv), ]
        return new_urls + urls

    def upload_csv(self, request):

        if request.method == "POST":
            csv_file = request.FILES["csv_upload"]

            if not csv_file.name.endswith('.csv'):
                messages.warning(request, 'The wrong file type was uploaded')
                return HttpResponseRedirect(request.path_info)

            file_data = csv_file.read().decode("utf-8")
            csv_data = file_data.split("\n")

            for i,x in enumerate(csv_data):
                fields = x.split(",")
                if fields[0] != "":
                    created = ErrorSignature.objects.update_or_create(
                        signature=fields[0],
                        readable_sig=fields[1],
                    )
            url = reverse('admin:index')
            return HttpResponseRedirect(url)

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/error_signature_upload.html", data)

class CsvImportForm(forms.Form):
    csv_upload = forms.FileField(label="Upload a CSV file")

class OptimalSolutionAdmin(admin.ModelAdmin):
    list_display = ('readable_sig', 'optimal_solution')
    search_fields = ['err_signature__signature']
    #exclude = ('cleaned_error_msg',)

    def readable_sig(self, obj):
        return obj.err_signature.signature

    readable_sig.short_description = 'Error Signature'

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [path('upload-csv/', self.upload_csv), ]
        return new_urls + urls

    def upload_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES.get("csv_upload")

            if not csv_file or not csv_file.name.endswith('.csv'):
                messages.warning(request, 'The wrong file type was uploaded')
                return HttpResponseRedirect(request.path_info)

            # Read CSV properly
            file_data = csv_file.read().decode("utf-8")
            csv_reader = csv.reader(StringIO(file_data))

            # Fetch error signatures into dict for faster lookup
            signatures = dict(ErrorSignature.objects.values_list("signature", "id"))

            # Fetch existing cleaned_error_msg to avoid duplicates
            existing_msgs = set(
                OptimalSolution.objects.values_list("cleaned_error_msg", flat=True)
            )

            # Ensure UnknownErrSig exists
            unknown_sig, _ = ErrorSignature.objects.get_or_create(signature="UnknownErrSig")

            processed, created_count, skipped = 0, 0, 0

            for i, fields in enumerate(csv_reader, start=1):
                if not fields or not fields[0].strip():
                    continue

                cleaned_msg = fields[0].strip()              # Column A
                solution_text = fields[1].strip() if len(fields) > 1 else ""  # Column B

                processed += 1

                if cleaned_msg in existing_msgs:
                    skipped += 1
                    continue

                # Match signature
                match_id = next((sid for sig, sid in signatures.items() if sig in cleaned_msg), None)
                sig_obj = ErrorSignature.objects.get(id=match_id) if match_id else unknown_sig

                OptimalSolution.objects.create(
                    cleaned_error_msg=cleaned_msg,
                    optimal_solution=solution_text,
                    err_signature=sig_obj,
                    updated_date=timezone.now(),
                )
                created_count += 1

            messages.success(
                request,
                f"Processed {processed} rows. Created {created_count} new records. Skipped {skipped} duplicates."
            )

            return HttpResponseRedirect(
                reverse('admin:restapi_optimalsolution_changelist')
            )

        form = CsvImportForm()
        data = {"form": form}
        return render(request, "admin/error_signature_upload.html", data)

    def automate_admin_upload(self):
        # Example method to simulate Selenium interaction after a CSV upload
        driver = webdriver.Chrome()  # Assuming Chrome driver, adjust as necessary
        driver.get('http://localhost:8000/admin/')  # Replace with your Django admin URL

        # Log in as admin
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        password_field = driver.find_element(By.NAME, 'password')

        username_field.send_keys('admin')  # Replace with your admin username
        password_field.send_keys('password')  # Replace with your admin password
        password_field.submit()

        # Navigate to the OptimalSolution admin page
        driver.get('http://localhost:8000/admin/app_name/optimalsolution/')

        # Wait until the page is loaded, and upload the CSV
        upload_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, 'Upload CSV'))  # Assuming a link text for CSV upload
        )
        upload_button.click()

        # Wait for the upload form and interact with it
        csv_file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'csv_upload'))  # Adjust based on your form field
        )
        csv_file_input.send_keys('/path/to/your/file.csv')  # Provide the path to your CSV file
        csv_file_input.submit()

        # Wait for the success message or next page to load
        success_message = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'success-message'))  # Adjust based on actual success message class
        )

        print("CSV uploaded successfully!")
        driver.quit()  # Don't forget to close the driver after the test!


# class TagMappingAdmin(admin.ModelAdmin):
#     model = TagMapping
#     ordering = ('tag_name',)
#     list_display = ['tag_name','train_name','suite_name']
#     search_fields = ['tag_name','train_name','suite_name']
#
#
# class SuiteTagAdmin(admin.ModelAdmin):
#     model = SuiteTag
#     ordering = ('tag_name',)
#     list_display = ['tag_name']
#     search_fields = ['tag_name']


admin.site.register(Trainlogdata, TrainlogdataAdmin)
admin.site.register(AllBranch, AllBranchAdmin)
admin.site.register(OptimalSolution, OptimalSolutionAdmin)
admin.site.register(ErrorSignature, ErrorSignatureAdmin)
admin.site.register(SquadDetails, SuiteDetailAdmin)
# admin.site.register(TagMapping, TagMappingAdmin)
# admin.site.register(SuiteTag, SuiteTagAdmin)
