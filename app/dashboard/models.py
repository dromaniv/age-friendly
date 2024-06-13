from django.db import models
from django.conf import settings


class AppSettings(models.Model):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)

    APPEARANCE_CHOICES = [
        ("light", "Light"),
        ("dark", "Dark"),
    ]

    appearance = models.CharField(
        max_length=100, default="light", choices=APPEARANCE_CHOICES
    )

    admin_level = models.IntegerField(default=9)

    heatmap_file = models.FileField(
        upload_to=settings.STATICFILES_DIRS[0], null=True, blank=True, default="heatmap.xlsx"
    )

    benches_file = models.FileField(
        upload_to=settings.STATICFILES_DIRS[0], null=True, blank=True
    )

    good_color = models.CharField(max_length=100, default="#24693D")
    okay_color = models.CharField(max_length=100, default="#6DB463")
    bad_color = models.CharField(max_length=100, default="#F57965")
    one_color = models.CharField(max_length=100, default="#E64E4B")
    empty_color = models.CharField(max_length=100, default="#A3123A")

    def save(self, *args, **kwargs):
        # Check if the object already exists and has a heatmap file
        if self.pk and self.heatmap_file:
            print(self.heatmap_file)
            try:
                # Get the existing instance from the database
                old_instance = AppSettings.objects.get(pk=self.pk)
                # If the new file is different from the old one, delete the old file
                if old_instance.heatmap_file != self.heatmap_file:
                    old_instance.heatmap_file.delete(save=False)
                    old_instance.heatmap_file.name = None
            except AppSettings.DoesNotExist:
                # If the object does not exist in the database yet, pass
                pass
        if self.pk and self.benches_file:
            try:
                # Get the existing instance from the database
                old_instance = AppSettings.objects.get(pk=self.pk)
                # If the new file is different from the old one, delete the old file
                if old_instance.benches_file != self.benches_file:
                    old_instance.benches_file.delete(save=False)
                    old_instance.benches_file.name = None
            except AppSettings.DoesNotExist:
                # If the object does not exist in the database yet, pass
                pass

        # Save the instance
        super(AppSettings, self).save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "App Settings"
