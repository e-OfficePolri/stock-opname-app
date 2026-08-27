import streamlit as st
import pandas as pd
from datetime import datetime
from db_utils import jalankan_query
from utils import check_login, tampilkan_sidebar, card_container
from services import sinkronisasi_riwayat_keluar

st.set_page_config(page_title="Barang Keluar - Stock Opname Setum Polri", page_icon="📤", layout="wide")

check_login()
tampilkan_sidebar()

st.title("📤 Input Barang Keluar")
st.write("---")
    
daftar_db = jalankan_query("SELECT kode_barang, nama_barang FROM barang ORDER BY LENGTH(kode_barang) ASC, kode_barang ASC")
daftar_barang = [f"{b[0]} - {b[1]}" for b in daftar_db] if daftar_db else []
    
if not daftar_barang:
    st.info("Belum ada data barang di sistem.")
else:
    pilihan_barang = st.selectbox("Pilih Barang Keluar:", daftar_barang)
    nama_barang = pilihan_barang.split(" - ")[1]
    kd_brg, stok_sekarang, sat_brg = jalankan_query("SELECT kode_barang, stok_sistem, satuan FROM barang WHERE nama_barang = %s", (nama_barang,))[0]
        
    with st.form(f"form_keluar_{nama_barang.replace(' ', '_')}", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1: st.text_input("Stok Tersedia Saat Ini:", value=f"{stok_sekarang} {sat_brg}", disabled=True)
        with col2: jumlah_keluar = st.number_input("Jumlah Barang Keluar:", min_value=1, step=1)
            
        if jumlah_keluar > stok_sekarang:
            st.warning("⚠️ **Peringatan:** Jumlah melebihi stok tersedia!")
                
        tanggal_keluar = st.date_input("Tanggal Keluar:", value=datetime.now().date())
        tujuan_subbag = st.selectbox("Tujuan Pengeluaran / Sub Bagian:", ["SUBBAGRENMIN", "SUBBAGTAKAH", "SUBBAGBINSET", "SUBBAGARSIP", "SUBBAGUM", "KANPOS", "URKEU"])
        input_catatan = st.text_input("Catatan Tambahan (Opsional):").strip()
            
        if st.form_submit_button("Simpan Transaksi Keluar", use_container_width=True):
            if jumlah_keluar > stok_sekarang:
                st.error("Gagal! Stok tidak mencukupi.")
            else:
                keterangan_final = f"Tujuan: {tujuan_subbag}" + (f" ({input_catatan})" if input_catatan else "")
                jalankan_query("UPDATE barang SET stok_sistem = %s WHERE nama_barang = %s", (stok_sekarang - jumlah_keluar, nama_barang), commit=True)
                jalankan_query("INSERT INTO riwayat (kode_barang, nama_barang, jenis_transaksi, jumlah, satuan, tanggal, keterangan) VALUES (%s, %s, 'KELUAR', %s, %s, %s, %s)", (kd_brg, nama_barang, jumlah_keluar, sat_brg, tanggal_keluar.strftime("%Y-%m-%d"), keterangan_final), commit=True)
                st.success("Transaksi keluar berhasil!")
                st.rerun()

# --- TABEL RIWAYAT + FITUR FILTER, EDIT & DELETE ---
st.write("---")
st.subheader("📜 Riwayat Khusus Barang Keluar")
    
raw_riwayat = jalankan_query("SELECT id, kode_barang, nama_barang, jumlah, tanggal, keterangan FROM riwayat WHERE jenis_transaksi = 'KELUAR' ORDER BY id DESC LIMIT 100")
    
if not raw_riwayat:
    st.info("Belum ada riwayat transaksi keluar.")
else:
    df_riwayat = pd.DataFrame(raw_riwayat, columns=["ID Transaksi", "Kode Barang", "Nama Barang", "Jumlah", "Tanggal", "Keterangan/Tujuan"])
    
    # --- FITUR FILTER ---
    st.write("🔍 **Filter Riwayat:**")
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        search_query = st.text_input("Cari Nama Barang / Sub Bagian / Kode:", placeholder="Ketik kata kunci...", key="search_keluar").strip().upper()
    with col_f2:
        filter_date = st.date_input("Filter Berdasarkan Tanggal:", value=None, key="date_keluar")
            
    # Terapkan filter pada DataFrame
    if search_query:
        df_riwayat = df_riwayat[df_riwayat["Nama Barang"].str.contains(search_query, na=False) | df_riwayat["Kode Barang"].str.contains(search_query, na=False) | df_riwayat["Keterangan/Tujuan"].str.contains(search_query, na=False)]
    if filter_date:
        df_riwayat = df_riwayat[df_riwayat["Tanggal"] == filter_date.strftime("%Y-%m-%d")]
            
    # --- LOGIKA PAGINATION ---
    baris_per_halaman = 10
    total_data = len(df_riwayat)
    total_halaman = (total_data - 1) // baris_per_halaman + 1 if total_data > 0 else 1
    
    # UI untuk memilih halaman
    col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
    with col_p1:
        st.write(f"Total: **{total_data}** riwayat")
    with col_p2:
        # Gunakan number_input untuk berpindah halaman
        halaman_sekarang = st.number_input("Halaman", min_value=1, max_value=total_halaman, step=1, key="halaman_keluar")
    
    # Memotong (slicing) data untuk halaman yang dipilih
    indeks_awal = (halaman_sekarang - 1) * baris_per_halaman
    indeks_akhir = indeks_awal + baris_per_halaman
    df_halaman_ini = df_riwayat.iloc[indeks_awal:indeks_akhir]
    
    st.caption("💡 *Klik ganda untuk mengedit Jumlah/Keterangan. Pilih baris lalu klik ikon Tong Sampah atau tekan Delete untuk menghapus.*")
        
    # Tampilkan HANYA data pada halaman ini di editor
    edited_df = st.data_editor(
        df_halaman_ini, 
        disabled=["ID Transaksi", "Kode Barang", "Nama Barang", "Tanggal"], 
        num_rows="dynamic", 
        hide_index=True, 
        use_container_width=True, 
        key=f"editor_keluar_hal_{halaman_sekarang}" # Key dinamis agar tidak error saat ganti halaman
    )
        
    if st.button("SINKRONISASI PERUBAHAN & PENGHAPUSAN KELUAR", type="primary", use_container_width=True):
        set_id_sekarang = set(edited_df["ID Transaksi"].tolist())
        # PENTING: Gunakan df_halaman_ini agar sistem tahu id yang terlihat di layar saja
        id_terlihat = df_halaman_ini["ID Transaksi"].tolist()
        
        # Panggil fungsi aman dari db_utils
        sukses, pesan = sinkronisasi_riwayat_keluar(raw_riwayat, id_terlihat, set_id_sekarang, edited_df)
        
        if sukses:
            st.success(pesan)
            st.rerun()
        else:
            st.error(pesan)
