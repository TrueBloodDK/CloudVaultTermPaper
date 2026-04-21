/* SecureVault — клиентский JS */

// ── Модал загрузки ──

function openUploadModal() {
  document.getElementById('upload-modal').style.display = 'flex';
}
function closeUploadModal() {
  document.getElementById('upload-modal').style.display = 'none';
}

// ── Модал доступа ──

function openShareModal(fileId, fileName) {
  document.getElementById('share-modal').style.display = 'flex';
  document.getElementById('share-file-name').textContent = fileName;
  document.getElementById('share-form').action = `/files/${fileId}/share/`;
}
function closeShareModal() {
  document.getElementById('share-modal').style.display = 'none';
}

// Закрытие по клику на фон
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('modal-backdrop')) {
    e.target.style.display = 'none';
  }
});

// Закрытие по Escape
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-backdrop').forEach(m => {
      m.style.display = 'none';
    });
  }
});

// ── Drag-and-drop зона ──

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const filePreview = document.getElementById('file-preview');
const previewName = document.getElementById('preview-name');
const previewSize = document.getElementById('preview-size');

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' Б';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ';
  return (bytes / (1024 * 1024)).toFixed(1) + ' МБ';
}

function showPreview(file) {
  previewName.textContent = file.name;
  previewSize.textContent = formatSize(file.size);
  if (filePreview) filePreview.style.display = 'flex';
  if (dropZone) dropZone.style.display = 'none';
}

if (fileInput) {
  fileInput.addEventListener('change', function() {
    if (this.files[0]) showPreview(this.files[0]);
  });
}

if (dropZone) {
  dropZone.addEventListener('dragover', function(e) {
    e.preventDefault();
    this.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', function() {
    this.classList.remove('drag-over');
  });
  dropZone.addEventListener('drop', function(e) {
    e.preventDefault();
    this.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && fileInput) {
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;
      showPreview(file);
    }
  });
}

// ── Автоскрытие сообщений ──

document.querySelectorAll('.message').forEach(function(msg) {
  setTimeout(function() {
    msg.style.transition = 'opacity 0.4s';
    msg.style.opacity = '0';
    setTimeout(function() { msg.remove(); }, 400);
  }, 4000);
});
