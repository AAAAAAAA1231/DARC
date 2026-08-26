const btn = document.getElementById("runBtn");
if (btn) {
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.textContent = "正在运行 Walk-Forward 与蒙特卡洛…";
    try {
      const res = await fetch("/api/run", { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      window.location.reload();
    } catch (err) {
      btn.disabled = false;
      btn.textContent = "运行失败，点击重试";
      alert(err);
    }
  });
}
