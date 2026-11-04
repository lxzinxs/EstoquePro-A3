from django.contrib import admin
from django.urls import include, path

from inventory import views as v
from inventory.auth_views import ConfiguredPasswordResetView, ProtectedLoginView

urlpatterns = [
    path("products/<int:pk>/alert/", v.reorder_level, name="reorder-level"),
    path(
        "accounts/password_reset/",
        ConfiguredPasswordResetView.as_view(),
        name="password_reset",
    ),
    path("accounts/login/", ProtectedLoginView.as_view(), name="login"),
    path("admin/", admin.site.urls),
    path("accounts/signup/", v.signup, name="signup"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("business/new/", v.business, name="new-business"),
    path("brand/", v.branding, name="branding"),
    path("plans/", v.plans, name="plans"),
    path("subscription/", v.subscription, name="subscription"),
    path("barcode/", v.barcode, name="barcode"),
    path("reorder/<int:pk>/", v.suggested_order, name="reorder"),
    path("", v.dashboard, name="dashboard"),
    path("switch/", v.switch, name="switch"),
    path("list/<str:kind>/", v.listing, name="listing"),
    path("new/<str:kind>/", v.new_record, name="new-record"),
    path(
        "products/<int:pk>/edit/",
        v.new_record,
        {"kind": "products"},
        name="edit-product",
    ),
    path("move/", v.movement, name="movement"),
    path("batch/", v.batch, name="batch"),
    path("transfer/", v.transfer, name="transfer"),
    path("action/<str:kind>/<int:pk>/", v.action, name="action"),
    path("payment/<int:pk>/", v.payment, name="payment"),
    path("nfe/", v.nfe, name="nfe"),
    path("team/new/", v.member, name="add-member"),
    path("team/<int:pk>/", v.member, name="membership-edit"),
    path("analysis/", v.analysis, name="analysis"),
    path("report/<str:fmt>/", v.report, name="report"),
    path("queue/<str:kind>/", v.queue, name="queue"),
    path("files/<int:pk>/", v.job_file, name="job-file"),
    path("share/<int:pk>/", v.share_order, name="order-share"),
    path("labels/", v.labels, name="labels"),
    path("notifications/", v.notifications, name="notifications"),
]
