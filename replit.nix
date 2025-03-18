{pkgs}: {
  deps = [
    pkgs.rdkafka
    pkgs.krb5
    pkgs.postgresql
    pkgs.openssl
  ];
}
