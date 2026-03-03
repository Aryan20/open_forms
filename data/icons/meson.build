application_id = 'in.aryank.openforms'

scalable_dir = 'hicolor' / 'scalable' / 'apps'
install_data(
  scalable_dir / ('@0@.svg').format(application_id),
  install_dir: get_option('datadir') / 'icons' / scalable_dir
)

symbolic_dir = 'hicolor' / 'symbolic' / 'apps'
install_data(
  symbolic_dir / ('@0@-symbolic.svg').format(application_id),
  install_dir: get_option('datadir') / 'icons' / symbolic_dir
)

png_128_dir = 'hicolor' / '128x128' / 'apps'
install_data(
  png_128_dir / ('@0@.png').format(application_id),
  install_dir: get_option('datadir') / 'icons' / png_128_dir
)

png_48_dir = 'hicolor' / '48x48' / 'apps'
install_data(
  png_48_dir / ('@0@.png').format(application_id),
  install_dir: get_option('datadir') / 'icons' / png_48_dir
)
