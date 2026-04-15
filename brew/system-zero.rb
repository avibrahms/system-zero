class SystemZero < Formula
  desc "One-click autonomy and self-improvement for any repository"
  homepage "https://systemzero.dev"
  url "https://files.pythonhosted.org/packages/source/s/system-zero/system_zero-0.1.0.tar.gz"
  sha256 "6cf1be1a819a9ff622b9c54dc53b67d3dee94d21480be3cf0acffb58f51269ae"
  license "Apache-2.0"
  depends_on "pipx"

  def install
    (bin/"sz").write <<~EOS
      #!/usr/bin/env bash
      exec "#{Formula["pipx"].opt_bin}/pipx" run --spec system-zero==0.1.0 sz "$@"
    EOS
  end

  test do
    assert_match "0.1.0", shell_output("#{bin}/sz --version")
  end
end
