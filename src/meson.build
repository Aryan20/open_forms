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
conf.set('PYTHON', python.find_installation('python3').full_path())
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
  'page.py'
]

install_data(open_forms_sources, install_dir: moduledir)
