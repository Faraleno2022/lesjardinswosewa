"""
URL configuration for ecole_moderne project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.views.generic import TemplateView, RedirectView
from .static_views import serve_static_no_cache
from .activation_views import activer_licence
from .desktop_views import arreter_application
from utilisateurs.license_api import activate_license, verify_license
from notes.rapport_scolaire import rapport_scolaire_recherche, rapport_scolaire_detail, rapport_scolaire_pdf, rapport_scolaire_recu_pdf, rapport_scolaire_classes_ajax


def google_site_verification(request):
    return HttpResponse(
        "google-site-verification: google10babad53f3eade7.html",
        content_type="text/html",
    )


def robots_txt(request):
    content = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /utilisateurs/",
        "Disallow: /eleves/",
        "Disallow: /paiements/",
        "Disallow: /depenses/",
        "Disallow: /salaires/",
        "Disallow: /notes/",
        "Disallow: /chatbot/",
        "Sitemap: https://www.myschoolgn.space/sitemap.xml",
        "",
    ])
    return HttpResponse(content, content_type="text/plain")


def sitemap_xml(request):
    urls = [
        ("https://www.myschoolgn.space/", "1.0"),
        ("https://www.myschoolgn.space/fonctionnalites/", "0.9"),
        ("https://www.myschoolgn.space/rapport-scolaire/", "0.8"),
        ("https://www.myschoolgn.space/contact/", "0.8"),
        ("https://www.myschoolgn.space/demo/", "0.8"),
        ("https://www.myschoolgn.space/tarifs/", "0.6"),
    ]
    items = "\n".join(
        f"  <url><loc>{loc}</loc><changefreq>weekly</changefreq><priority>{priority}</priority></url>"
        for loc, priority in urls
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{items}
</urlset>
"""
    return HttpResponse(xml, content_type="application/xml")


urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('activer/', activer_licence, name='activer_licence'),
    path('desktop/arreter/', arreter_application, name='arreter_application'),
    path('api/v1/license/activate', activate_license, name='license_api_activate'),
    path('api/v1/license/activate/', activate_license, name='license_api_activate_slash'),
    path('api/v1/license/verify', verify_license, name='license_api_verify'),
    path('api/v1/license/verify/', verify_license, name='license_api_verify_slash'),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('index/', TemplateView.as_view(template_name='home.html'), name='index'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    path('fonctionnalites/', TemplateView.as_view(template_name='public/fonctionnalites.html'), name='fonctionnalites'),
    path('tarifs/', TemplateView.as_view(template_name='public/tarifs.html'), name='tarifs'),
    path('contact/', TemplateView.as_view(template_name='public/contact.html'), name='contact'),
    path('demo/', TemplateView.as_view(template_name='public/demo.html'), name='demo'),
    path('google10babad53f3eade7.html', google_site_verification, name='google_site_verification'),
    # Rapport scolaire public (espace parent, pas de login)
    path('rapport-scolaire/', rapport_scolaire_recherche, name='rapport_scolaire'),
    path('rapport-scolaire/detail/', rapport_scolaire_detail, name='rapport_scolaire_detail'),
    path('rapport-scolaire/pdf/', rapport_scolaire_pdf, name='rapport_scolaire_pdf'),
    path('rapport-scolaire/recu/<int:paiement_id>/pdf/', rapport_scolaire_recu_pdf, name='rapport_scolaire_recu_pdf'),
    path('rapport-scolaire/ajax/classes/', rapport_scolaire_classes_ajax, name='rapport_scolaire_classes_ajax'),
    # Friendly redirects for legacy/mistyped routes under /ecole/
    path('ecole/inscription/', RedirectView.as_view(pattern_name='home', permanent=False)),
    path('ecole/inscription-complete/', RedirectView.as_view(pattern_name='home', permanent=False)),
    path('ecole/verifier-statut/', RedirectView.as_view(pattern_name='home', permanent=False)),
    path('eleves/', include('eleves.urls')),
    path('paiements/', include('paiements.urls')),
    path('depenses/', include('depenses.urls')),
    path('salaires/', include('salaires.urls')),
    path('administration/', include('administration.urls')),
    path('utilisateurs/', include('utilisateurs.urls')),
    path('rapports/', include('rapports.urls')),
    path('bus/', include('bus.urls')),
    path('notes/', include('notes.urls')),
    path('notes/presence/', include('presence.urls')),
    path('abonnements/', include('abonnements.urls')),
    path('chatbot/', include('chatbot.urls')),
    path('api/v1/sync/', include('synchronisation.urls')),
]

# Servir les fichiers STATIC et MEDIA en développement
if settings.DEBUG:
    # Route spéciale pour les images sans cache (rechargement automatique)
    urlpatterns += [
        re_path(r'^static/images/(?P<path>.*)$', serve_static_no_cache, name='static_images_no_cache'),
    ]
    # Routes normales pour les autres fichiers statiques
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
