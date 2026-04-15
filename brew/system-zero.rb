class SystemZero < Formula
  desc "One-click autonomy and self-improvement for any repository"
  homepage "https://systemzero.dev"
  url "https://files.pythonhosted.org/packages/source/s/system-zero/system_zero-0.1.0.tar.gz"
  sha256 "REPLACE_AFTER_PYPI_PUBLISH"
  license "Apache-2.0"
  depends_on "python@3.12"

  def install
    system Formula["python@3.12"].opt_bin/"python3", "-m", "venv", libexec
    system libexec/"bin/python3", "-m", "pip", "install", "--upgrade", "pip"
    system libexec/"bin/python3", "-m", "pip", "install", "system-zero==0.1.0"
    bin.install_symlink libexec/"bin/sz"
  end

  test do
    assert_match "0.1.0", shell_output("#{bin}/sz --version")
  end
end
