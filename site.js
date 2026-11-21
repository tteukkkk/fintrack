/* Showcase Pages V2 — tema compartilhado com o portfolio e trocas reais de screenshots. */
(()=>{
 const root=document.documentElement;
 const toggle=document.getElementById('theme-toggle');
 const dialog=document.getElementById('lightbox');
 const full=document.getElementById('full-image');
 const dialogTitle=document.getElementById('lightbox-title');
 const images=[...document.querySelectorAll('img[data-light][data-dark]')];
 const filterButtons=[...document.querySelectorAll('button[data-filter]')];
 let activeButton=null;

 // Preferimos a mesma configuração do portfolio principal (todos estão no mesmo domínio).
 function currentTheme(){return root.dataset.theme==='dark'?'dark':'light'}
 function imagePath(img){return currentTheme()==='dark'?img.dataset.dark:img.dataset.light}
 function fallbackPath(img){return currentTheme()==='dark'?img.dataset.fallbackDark:img.dataset.fallbackLight}
 function applyImage(img){
   img.classList.remove('is-preview-adapted');
   img.dataset.fallbackTried='0';
   img.src=imagePath(img);
 }
 images.forEach(img=>{
   img.addEventListener('error',()=>{
     if(img.dataset.fallbackTried==='1')return;
     img.dataset.fallbackTried='1';
     const fallback=fallbackPath(img);
     if(!fallback)return;
     // Enquanto não há screenshot nativo do tema, adapta visualmente a captura original.
     img.classList.toggle('is-preview-adapted',currentTheme()==='dark');
     img.src=fallback;
   });
 });
 function updateTheme(){
   const dark=currentTheme()==='dark';
   toggle.textContent=dark?'☀':'☾';
   toggle.setAttribute('aria-label',dark?'Ativar modo claro':'Ativar modo escuro');
   toggle.title=dark?'Mudar para o modo claro':'Mudar para o modo escuro';
   document.querySelector('meta[name="theme-color"]')?.setAttribute('content',dark?'#10141a':'#f8f9fb');
   images.forEach(applyImage);
   if(dialog.open&&activeButton)showFull(activeButton);
 }
 toggle?.addEventListener('click',()=>{
   root.dataset.theme=currentTheme()==='dark'?'light':'dark';
   try{localStorage.setItem('portfolio-theme',root.dataset.theme)}catch(e){}
   updateTheme();
 });
 updateTheme();

 function showFull(button){
   activeButton=button;
   const thumb=button.querySelector('img');
   full.src=thumb.currentSrc||thumb.src;
   full.alt=thumb.alt;
   full.className=thumb.className;
   dialogTitle.textContent=button.closest('.screen-card').querySelector('h3')?.textContent||'Captura ampliada';
 }
 document.querySelectorAll('.screen-open').forEach(button=>{
   button.addEventListener('click',()=>{showFull(button);dialog.showModal()});
   const img=button.querySelector('img');
   img.addEventListener('load',()=>{if(activeButton===button&&dialog.open)showFull(button)});
 });
 document.getElementById('lightbox-close')?.addEventListener('click',()=>dialog.close());
 dialog?.addEventListener('click',event=>{if(event.target===dialog)dialog.close()});
 dialog?.addEventListener('close',()=>{activeButton=null});
 filterButtons.forEach(button=>button.addEventListener('click',()=>{
   filterButtons.forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
   const type=button.dataset.filter;
   let visible=0;
   document.querySelectorAll('.screen-card').forEach(card=>{
     const show=type==='all'||card.dataset.kind===type;
     card.hidden=!show;if(show)visible++;
   });
   document.getElementById('screen-count').textContent=String(visible);
 }));
})();
