from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    """A CRM user. Logs in with email; `role` decides what they can see and do."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        REP = "rep", "Sales rep"

    username = None  # removed: email is the login
    email = models.EmailField("email address", unique=True)
    first_name = models.CharField("first name", max_length=150)  # required, unlike AbstractUser
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.REP)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name"]  # asked by createsuperuser, besides email and password

    objects = UserManager()

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.email

    def clean(self):
        # Forms run clean() before their unique check, so lowercase here too.
        # Otherwise "Rahim@x.com" passes the check and save() crashes on the duplicate.
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()

    def save(self, *args, **kwargs):
        # One rule for every path (admin, shell, API): emails are stored lowercase.
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)
