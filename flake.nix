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
          pythonEnv = python.withPackages (ps: with ps; [
            flask
            ipython
            tiktoken
            pikepdf
            pypdf
            requests
          ]);
          python313 = pkgs.python313;
          python313Env = python313.withPackages (ps: with ps; [
            tiktoken
          ]);

          pepysPackages = pkgs.callPackages ./nix/packages.nix {
            inherit pythonEnv;
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
            default = pepysPackages.pepys-server;
            pdfvisualizer-api = pepysPackages.pdfvisualizer-api;
            pepys-people-db = pepysPackages.pepys-people-db;
          };
          apps = {
            default = flake-utils.lib.mkApp { drv = pepysPackages.pepys-server; };
            pdfvisualizer-api = flake-utils.lib.mkApp { drv = pepysPackages.pdfvisualizer-api; };
          };
          devShells.default = pkgs.mkShell {
            buildInputs = [
              pythonEnv
            ] ++ devTools;
            shellHook = ''
              export IPYTHONDIR="$PWD/.ipython"
            '';
          };
          devShells.tiktoken = pkgs.mkShell {
            buildInputs = [
              python313Env
            ];
          };
        }
      );
}
