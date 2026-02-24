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

        devTools = with pkgs; [
          pyright
          ruff
          python3Packages.black
          python3Packages.mypy
          python3Packages.isort
        ];
      in
      {
        packages.default = pepys-server;
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
