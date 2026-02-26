{ pkgs, pythonEnv }:

let
  src = ../.;
in
{
  pepys-server = pkgs.stdenv.mkDerivation {
    pname = "pepys-server";
    version = "0.1.0";
    src = src;
    nativeBuildInputs = [ pkgs.makeWrapper ];
    buildInputs = [ pythonEnv ];
    buildPhase = ''
      runHook preBuild
      ${pythonEnv}/bin/python init_people_db.py
      runHook postBuild
    '';
    installPhase = ''
      runHook preInstall
      install -d $out/share/pepys
      cp -r site diary_by_date app.py $out/share/pepys/
      install -m 0644 people.sqlite $out/share/pepys/people.sqlite
      makeWrapper ${pythonEnv}/bin/python $out/bin/pepys-server \
        --chdir $out/share/pepys \
        --add-flags app.py
      runHook postInstall
    '';
  };

  pdfvisualizer-api = pkgs.stdenv.mkDerivation {
    pname = "pdfvisualizer-api";
    version = "0.1.0";
    src = src;
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

  pdf-split-pages = pkgs.writeShellApplication {
    name = "pdf-split-pages";
    runtimeInputs = [ pkgs.poppler ];
    text = ''
      set -euo pipefail

      if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
        echo "Usage: pdf-split-pages input.pdf [output-pattern]" >&2
        echo "Default output pattern: page-%03d.pdf" >&2
        exit 2
      fi

      input="$1"
      output_pattern="''${2:-page-%03d.pdf}"

      pdfseparate "$input" "$output_pattern"
    '';
  };

  pepys-people-db = pkgs.stdenv.mkDerivation {
    pname = "pepys-people-db";
    version = "0.1.0";
    src = src;
    buildInputs = [ pythonEnv ];
    buildPhase = ''
      runHook preBuild
      ${pythonEnv}/bin/python init_people_db.py
      runHook postBuild
    '';
    installPhase = ''
      runHook preInstall
      install -d $out/share/pepys
      install -m 0644 people.sqlite $out/share/pepys/people.sqlite
      runHook postInstall
    '';
  };
}
