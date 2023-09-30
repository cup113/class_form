@cd %~dp0
@cd ..
call nuitka --output-dir=dist --enable-plugin=tk-inter --standalone --onefile --onefile-no-compression --disable-console --windows-icon-from-ico=build/favicon.ico  .\src\class_form.py
copy .\config.json dist\config.json
call marked .\README.md -o .\dist\README.html
call 7z a .\dist\class_form.zip .\dist\class_form.exe .\dist\config.json .\dist\README.html .\src
