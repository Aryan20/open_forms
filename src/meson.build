pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'open_forms'
gnome = import('gnome')

gnome.compile_resources('open_forms',
  'open_forms.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', '/usr/bin/env python3')
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'open_forms.in',
  output: 'open_forms',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

open_forms_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'form_page.py',
  'form_config.py',
  'page.py',
  'utils.py',
  'builder_page.py',
  'field_editor_row.py',
  'field_type_dialog.py',
  'form_model.py',
  'response_viewer.py',
  'kiosk_manager.py',
  'history_manager.py',
  'history_dialog.py',
]

install_data(open_forms_sources, install_dir: moduledir)

# Sync layer: pushes collected responses to Google Sheets or WebDAV/Nextcloud.
# Requires the network + secrets Flatpak permissions declared in the app manifest.
sync_sources = files(
  'sync/__init__.py',
  'sync/backend.py',
  'sync/queue.py',
  'sync/worker.py',
  'sync/google_sheets.py',
  'sync/webdav.py',
  'sync/keyring.py',
  'sync/settings.py',
)
install_data(sync_sources, install_dir: moduledir / 'sync')
install_data('sync_panel.py', install_dir: moduledir)
install_data('sync_settings_dialog.py', install_dir: moduledir)
