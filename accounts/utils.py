from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render


def paginate(request, qs, per=25):
    page = Paginator(qs, per).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    page.extra_qs = params.urlencode()
    return page


def model_form_view(request, form_class, *, instance=None, title, back, hint=""):
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect(back)
    return render(request, "form.html", {"form": form, "title": title, "back": back, "hint": hint})
