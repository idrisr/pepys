{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3;
        pythonEnv = python.withPackages (ps: with ps; [
          flask
          ipython
          pikepdf
          pypdf
          requests
        ]);

        pepys-server = pkgs.stdenv.mkDerivation {
          pname = "pepys-server";
          version = "0.1.0";
          src = ./.;
          nativeBuildInputs = [ pkgs.makeWrapper ];
          buildInputs = [ pythonEnv ];
          installPhase = ''
            runHook preInstall
            install -d $out/share/pepys
            cp -r site diary_by_date app.py $out/share/pepys/
            makeWrapper ${pythonEnv}/bin/python $out/bin/pepys-server \
              --chdir $out/share/pepys \
              --add-flags app.py
            runHook postInstall
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
            cp -r pdfvisualizer/api $out/share/pdfvisualizer/
            makeWrapper ${pythonEnv}/bin/python $out/bin/pdfvisualizer-api \
              --chdir $out/share/pdfvisualizer/api \
              --add-flags app.py
            runHook postInstall
          '';
        };

        devTools = with pkgs; [
          pyright
          ruff
          python3Packages.black
          python3Packages.mypy
          python3Packages.isort
        ];
      in
      {
        packages = {
          default = pepys-server;
          pdfvisualizer-api = pdfvisualizer-api;
        };
        apps = {
          default = flake-utils.lib.mkApp { drv = pepys-server; };
          pdfvisualizer-api = flake-utils.lib.mkApp { drv = pdfvisualizer-api; };
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
