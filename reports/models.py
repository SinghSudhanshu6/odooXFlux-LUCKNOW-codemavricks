from django.db import models


class MRRSnapshot(models.Model):
    date = models.DateField(unique=True)
    new = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expansion = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    contraction = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    churned = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_mrr = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["date"]

    @property
    def net_new(self):
        return self.new + self.expansion - self.contraction - self.churned
