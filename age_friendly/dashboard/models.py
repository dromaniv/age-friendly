from django.db import models


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

    heatmap_file = models.FileField(upload_to="static/", null=True, blank=True)

    def save(self, *args, **kwargs):
        # Check if the object already exists and has a heatmap file
        if self.pk and self.heatmap_file:
            try:
                # Get the existing instance from the database
                old_instance = AppSettings.objects.get(pk=self.pk)
                # If the new file is different from the old one, delete the old file
                if old_instance.heatmap_file != self.heatmap_file:
                    old_instance.heatmap_file.delete(save=False)
            except AppSettings.DoesNotExist:
                # If the object does not exist in the database yet, pass
                pass

        # Save the instance
        super(AppSettings, self).save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "App Settings"
