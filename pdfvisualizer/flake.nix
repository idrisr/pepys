{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachSystem
      [ "x86_64-linux" "aarch64-darwin" ]
      (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;
          pythonPackages = ps: with ps; [
            flask
            ipython
            numpy
            pikepdf
            torch
          ];
          pythonEnv = python.withPackages pythonPackages;

          webSrc = builtins.path {
            path = ./web;
            name = "pdfvisualizer-web-src";
            filter = path: type:
              let
                rel = pkgs.lib.removePrefix (toString ./web + "/") (toString path);
              in
                !(rel == "node_modules"
                  || rel == "dist"
                  || pkgs.lib.hasPrefix "node_modules/" rel
                  || pkgs.lib.hasPrefix "dist/" rel);
          };

          pdfvisualizer-web = pkgs.buildNpmPackage {
            pname = "pdfvisualizer-web";
            version = "0.1.0";
            src = webSrc;
            npmDepsHash = "sha256-xvXcOVo1nWFJQ9f3bOx3XThaTHwF/c05lL7tVcztlsU=";
            npmBuildScript = "build";
            installPhase = ''
              runHook preInstall
              mkdir -p $out/share/pdfvisualizer-web
              cp -r dist $out/share/pdfvisualizer-web/
              runHook postInstall
            '';
          };

          pdfvisualizer-web-server = pkgs.writeShellApplication {
            name = "pdfvisualizer-web";
            runtimeInputs = [ pkgs.python3 ];
            text = ''
              set -euo pipefail
              dist="${pdfvisualizer-web}/share/pdfvisualizer-web/dist"
              if [ ! -d "$dist" ]; then
                echo "Built UI not found in store." >&2
                exit 1
              fi
              port="''${PDFVIZ_WEB_PORT:-5173}"
              exec python -m http.server "$port" --directory "$dist"
            '';
          };

          pdfvisualizer-app = pkgs.writeShellApplication {
            name = "pdfvisualizer-app";
            runtimeInputs = [ pdfvisualizer-api ];
            text = ''
              set -euo pipefail
              export PDFVIZ_WEB_DIST="${pdfvisualizer-web}/share/pdfvisualizer-web/dist"
              exec pdfvisualizer-api
            '';
          };

          pdfvisualizer-api = pkgs.stdenv.mkDerivation {
            pname = "pdfvisualizer-api";
            version = "0.1.0";
            src = ./.;
            nativeBuildInputs = [ pkgs.makeWrapper ];
            buildInputs = [ pythonEnv ];
            installPhase = ''
              runHook preInstall
              install -d $out/share/pdfvisualizer
              cp -r api $out/share/pdfvisualizer/
              makeWrapper ${pythonEnv}/bin/python $out/bin/pdfvisualizer-api \
                --chdir $out/share/pdfvisualizer/api \
                --add-flags app.py
              runHook postInstall
            '';
          };

          pdfvisualizer-dev = pkgs.writeShellApplication {
            name = "pdfvisualizer-dev";
            runtimeInputs = [ pkgs.nodejs pdfvisualizer-api ];
            text = ''
              set -euo pipefail
              if [ ! -f "web/package.json" ]; then
                echo "Run from the pdfvisualizer directory (missing web/package.json)." >&2
                exit 1
              fi
              if [ ! -d "web/node_modules" ]; then
                echo "Missing web/node_modules. Run 'npm install' in web/ first." >&2
                exit 1
              fi

              pdfvisualizer-api &
              api_pid=$!
              trap 'kill ''${api_pid}' EXIT
              npm --prefix web run dev
            '';
          };

          devTools = with pkgs; [
            nodejs
            pyright
            ruff
            python3Packages.black
            python3Packages.mypy
            python3Packages.isort
          ];
        in
        {
          packages = {
            default = pythonEnv;
            pdfvisualizer-api = pdfvisualizer-api;
            pdfvisualizer-app = pdfvisualizer-app;
            pdfvisualizer-web = pdfvisualizer-web;
            pdfvisualizer-web-server = pdfvisualizer-web-server;
            pdfvisualizer-dev = pdfvisualizer-dev;
          };
          apps = {
            default = flake-utils.lib.mkApp { drv = pdfvisualizer-app; };
            pdfvisualizer-api = flake-utils.lib.mkApp { drv = pdfvisualizer-api; };
            pdfvisualizer-app = flake-utils.lib.mkApp { drv = pdfvisualizer-app; };
            pdfvisualizer-web = flake-utils.lib.mkApp { drv = pdfvisualizer-web-server; };
            pdfvisualizer-dev = flake-utils.lib.mkApp { drv = pdfvisualizer-dev; };
          };
          checks = {
            default = pythonEnv;
            pdfvisualizer-api = pdfvisualizer-api;
            pdfvisualizer-app = pdfvisualizer-app;
            pdfvisualizer-web = pdfvisualizer-web;
            pdfvisualizer-web-server = pdfvisualizer-web-server;
            pdfvisualizer-dev = pdfvisualizer-dev;
          };
          devShells.default = pkgs.mkShell {
            buildInputs = [
              pythonEnv
            ] ++ devTools;
            shellHook = ''
              export IPYTHONDIR="$PWD/.ipython"
            '';
          };
        }
      );
}
