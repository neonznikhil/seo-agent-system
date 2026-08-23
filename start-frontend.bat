@echo off
pushd "%~dp0frontend-next"
start "SEO Agent Frontend" npm run dev
popd
echo Frontend running at http://localhost:3000