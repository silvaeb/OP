// Contadores para instalações e sub-itens
let instalacaoCount = 0;
let empilhadeiraCounts = {};
let sistemaCounts = {};
let equipamentoCounts = {};

// Inicializar a primeira instalação e a matriz de pessoal ao carregar a página
document.addEventListener('DOMContentLoaded', function() {
    const temInstalacoesPreload = window.EDIT_MODE && window.PRELOAD_DATA && Array.isArray(window.PRELOAD_DATA.instalacoes) && window.PRELOAD_DATA.instalacoes.length > 0;

    // Só cria card vazio automaticamente quando não há instalações pré-carregadas
    if (typeof addInstalacao === 'function' && !temInstalacoesPreload) {
        addInstalacao(true); // evita toast automático ao carregar a página
    }
    if (typeof initPessoalMatrix === 'function') initPessoalMatrix();
    // Permitir digitar diretamente o total por posto
    document.querySelectorAll('.pessoa-total').forEach(el => el.removeAttribute('readonly'));

    // Se houver dados de pessoal no preload, preencher a matriz
    if (window.PRELOAD_DATA && Array.isArray(window.PRELOAD_DATA.pessoal)) {
        try {
            console.log('[PESSOAL] preload entries:', window.PRELOAD_DATA.pessoal.length);
            preencherMatrizPessoalPreload(window.PRELOAD_DATA.pessoal);
        } catch (err) {
            console.warn('Falha ao preencher matriz de pessoal do preload', err);
        }
    }
});

// ---- Pré-carregar matriz de pessoal a partir do backend ----
function mapPostoDisplayToKey(display) {
    if (!display) return '';
    const norm = display.toString().trim().toLowerCase();
    const mapa = {
        'coronel': 'coronel',
        'cel': 'coronel',
        'tenente-coronel': 'tenente_coronel',
        'tc': 'tenente_coronel',
        'major': 'major',
        'capitão': 'capitao',
        'capitao': 'capitao',
        '1º tenente': 'primeiro_tenente',
        '1o tenente': 'primeiro_tenente',
        'primeiro tenente': 'primeiro_tenente',
        '2º tenente': 'segundo_tenente',
        '2o tenente': 'segundo_tenente',
        'segundo tenente': 'segundo_tenente',
        'subtenente': 'subtenente',
        '1º sargento': 'primeiro_sargento',
        '1o sargento': 'primeiro_sargento',
        'primeiro sargento': 'primeiro_sargento',
        '2º sargento': 'segundo_sargento',
        '2o sargento': 'segundo_sargento',
        'segundo sargento': 'segundo_sargento',
        '3º sargento': 'terceiro_sargento',
        '3o sargento': 'terceiro_sargento',
        'terceiro sargento': 'terceiro_sargento',
        'cabo': 'cabo',
        'soldado': 'soldado',
        'sd': 'soldado'
    };
    return mapa[norm] || '';
}

function preencherMatrizPessoalPreload(pessoalList) {
    pessoalList.forEach(entry => {
        const postoKey = mapPostoDisplayToKey(entry.posto_graduacao || entry.posto || '');
        if (!postoKey) {
            console.warn('[PESSOAL] posto não mapeado no preload', entry.posto_graduacao || entry.posto);
            return;
        }
        const qtd = parseInt(entry.quantidade) || 0;
        if (!qtd) return;
        const tipo = (entry.tipo_servico || '').toLowerCase();
        const arma = entry.arma_quadro_servico || entry.arma || '';
        const espec = entry.especialidade || '';

        console.log('[PESSOAL] preload apply', { postoKey, tipo, arma, espec, qtd });

        const totalInput = document.querySelector(`tr[data-posto="${postoKey}"] .pessoa-total`);
        if (totalInput) {
            totalInput.value = (parseInt(totalInput.value) || 0) + qtd;
        }

        const allowedTipos = ['carreira', 'temporario'];
        if (allowedTipos.includes(tipo)) {
            const tipoInput = document.querySelector(`.pessoa-tipo-quantidade[data-posto="${postoKey}"][data-tipo="${tipo}"]`);
            if (tipoInput) {
                tipoInput.value = (parseInt(tipoInput.value) || 0) + qtd;
            }
            // Se houver especialidade/arma, cria linha
            if (arma || espec) {
                addEspecialidade(postoKey, tipo);
                const container = document.getElementById(`pessoalGroup_${postoKey}_${tipo}`) || document.getElementById(`pessoalSubdiv_${postoKey}`);
                const rows = container ? container.querySelectorAll('.pessoal-especialidade-row') : [];
                const row = rows[rows.length - 1];
                if (row) {
                    const armaSel = row.querySelector('.pessoa-arma');
                    if (armaSel) armaSel.value = arma;
                    const especSel = row.querySelector('.pessoa-especialidade');
                    if (especSel) especSel.value = espec;
                    const qtyInput = row.querySelector('.pessoa-quantidade');
                    if (qtyInput) qtyInput.value = qtd;
                }
                console.log('[PESSOAL] row added tipo', tipo, 'posto', postoKey, 'rows now', (container ? container.querySelectorAll('.pessoal-especialidade-row').length : 0));
            }
        } else {
            // Fallback: sem tipo (carreira/temporário) definido
            const container = document.getElementById(`pessoalSubdiv_${postoKey}`);
            if (container && (arma || espec)) {
                addEspecialidade(postoKey);
                const rows = container.querySelectorAll('.pessoal-especialidade-row');
                const row = rows[rows.length - 1];
                if (row) {
                    const armaSel = row.querySelector('.pessoa-arma');
                    if (armaSel) armaSel.value = arma;
                    const especSel = row.querySelector('.pessoa-especialidade');
                    if (especSel) especSel.value = espec;
                    const qtyInput = row.querySelector('.pessoa-quantidade');
                    if (qtyInput) qtyInput.value = qtd;
                }
                console.log('[PESSOAL] row added sem tipo posto', postoKey, 'rows now', rows.length);
            } else if (totalInput) {
                // Já somado no total; nada mais a fazer
            }
        }
    });

    // Recalcular totais
    document.querySelectorAll('tr[data-posto]').forEach(tr => {
        recalcPostTotals(tr.dataset.posto);
        const totalInput = tr.querySelector('.pessoa-total');
        if (totalInput) console.log('[PESSOAL] total after preload', tr.dataset.posto, totalInput.value);
    });
}

// Adicionar uma nova instalação (silent controla alerta no outro script)
function addInstalacao(silent) {
    const container = document.getElementById('instalacoesContainer');
    const template = document.getElementById('instalacaoTemplate');
    const clone = template.content.cloneNode(true);
    
    // Atualizar índices
    const instalacaoDiv = clone.querySelector('.instalacao-card');
    instalacaoDiv.dataset.index = instalacaoCount;
    instalacaoDiv.querySelector('.instalacao-numero').textContent = instalacaoCount + 1;
    
    // Atualizar todos os names e ids
    updateElementNames(clone, instalacaoCount);
    
    // Inicializar contadores para sub-itens desta instalação
    empilhadeiraCounts[instalacaoCount] = 0;
    sistemaCounts[instalacaoCount] = 0;
    equipamentoCounts[instalacaoCount] = 0;
    
    container.appendChild(clone);
    instalacaoCount++;

    // Atualizar contador oculto de instalações
    const countInput = document.getElementById('instalacoes_count');
    if (countInput) countInput.value = instalacaoCount;
}

// Remover uma instalação
function removeInstalacao(button) {
    const instalacaoCard = button.closest('.instalacao-card');
    if (instalacaoCard) {
        instalacaoCard.remove();
           updateElementNamesInExisting(instalacaoCard, instalacaoCount);
           renumberInstalacoes();
    }
}

// Renumerar instalações após remoção
function renumberInstalacoes() {
    const instalacoes = document.querySelectorAll('.instalacao-card');
    instalacaoCount = 0;
    
    instalacoes.forEach((instalacao, index) => {
        instalacao.dataset.index = instalacaoCount;
        instalacao.querySelector('.instalacao-numero').textContent = instalacaoCount + 1;
            updateElementNamesInExisting(instalacao, instalacaoCount);
        instalacaoCount++;
    });

    // Atualizar contador oculto de instalações
    const countInput = document.getElementById('instalacoes_count');
    if (countInput) countInput.value = instalacaoCount;
}

// Atualizar names em elementos recém-clonados
function updateElementNames(element, index) {
    const inputs = element.querySelectorAll('[name]');
    const labels = element.querySelectorAll('label[for]');
    
    inputs.forEach(input => {
        const name = input.getAttribute('name');
        if (name && name.includes('_0')) {
            input.setAttribute('name', name.replace('_0', `_${index}`));
        }
    });
    
    labels.forEach(label => {
        const forAttr = label.getAttribute('for');
        if (forAttr && forAttr.includes('_0')) {
            label.setAttribute('for', forAttr.replace('_0', `_${index}`));
        }
    });
    
    // Atualizar IDs e event handlers
    const previewElements = element.querySelectorAll('[id*="Preview0"]');
    previewElements.forEach(el => {
        const oldId = el.id;
        const newId = oldId.replace('0', index);
        el.id = newId;
    });
    
    const fileInputs = element.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        const oldOnChange = input.getAttribute('onchange');
        if (oldOnChange && oldOnChange.includes('0')) {
            input.setAttribute('onchange', oldOnChange.replace('0', index));
        }
    });
}

// Atualizar names em elementos existentes
function updateElementNamesInExisting(element, index) {
    const rewriteFirstIndex = (val) => {
        if (!val) return val;
        if (/\d+$/.test(val) && !val.includes('_')) {
            return val.replace(/\d+$/, `${index}`);
        }
        if (/_\d+/.test(val)) {
            return val.replace(/_(\d+)/, `_${index}`);
        }
        return val;
    };

    element.querySelectorAll('[name], [id], label[for]').forEach(el => {
        if (el.name) el.name = rewriteFirstIndex(el.name);
        if (el.id) el.id = rewriteFirstIndex(el.id);
        if (el.tagName === 'LABEL' && el.htmlFor) el.htmlFor = rewriteFirstIndex(el.htmlFor);
    });

    // Ajustar previews e inputs de foto de instalação
    const instFoto = element.querySelector('input[id^="instalacao_fotos_"]');
    const instPreview = element.querySelector('[id^="instalacaoPreview"]');
    if (instFoto) {
        if (instFoto.id) instFoto.id = rewriteFirstIndex(instFoto.id);
        if (instFoto.name) instFoto.name = rewriteFirstIndex(instFoto.name);
        const previewId = instPreview ? instPreview.id : `instalacaoPreview${index}`;
        instFoto.setAttribute('onchange', `previewImage(this, '${previewId}')`);
    }
    if (instPreview && instPreview.id) instPreview.id = rewriteFirstIndex(instPreview.id);
}

// Adicionar empilhadeira a uma instalação
function addEmpilhadeira(instalacaoIndex) {
    const container = document.getElementById(`empilhadeirasContainer${instalacaoIndex}`);
    if (!container) return;
    
    const template = document.getElementById('empilhadeiraTemplate');
    const clone = template.content.cloneNode(true);
    
    // Atualizar índices
    const subIndex = empilhadeiraCounts[instalacaoIndex] || 0;
    
    // Substituir placeholders
    const html = clone.querySelector('.sub-item').innerHTML;
    const updatedHtml = html
        .replace(/{{index}}/g, instalacaoIndex)
        .replace(/{{subIndex}}/g, subIndex);
    
    clone.querySelector('.sub-item').innerHTML = updatedHtml;
    
    container.appendChild(clone);
    empilhadeiraCounts[instalacaoIndex] = subIndex + 1;

    // Atualizar contador oculto correspondente
    const countInput = document.getElementById(`empilhadeiras_count_${instalacaoIndex}`);
    if (countInput) countInput.value = empilhadeiraCounts[instalacaoIndex];
}


// ==================== MATRIZ DE PESSOAL (NOVO) ====================
function updateTipoFromSpecialities(posto, tipo) {
    // soma as especialidades dentro do container do tipo e atualiza o input tipo
    try {
        const container = document.getElementById(`pessoalGroup_${posto}_${tipo}`);
        if (!container) return;
        const rows = container.querySelectorAll('.pessoal-especialidade-row');
        let sum = 0;
        rows.forEach(r => sum += parseInt(r.querySelector('.pessoa-quantidade').value) || 0);
        const tipoInput = document.querySelector(`.pessoa-tipo-quantidade[data-posto="${posto}"][data-tipo="${tipo}"]`);
        if (tipoInput) tipoInput.value = sum;
        recalcPostTotals(posto);
    } catch (err) {
        console.error('Erro updateTipoFromSpecialities:', err);
    }
}

function recalcPostTotals(posto) {
    try {
        const tr = document.querySelector(`tr[data-posto="${posto}"]`);
        if (!tr) return;
        const tipoInputs = tr.querySelectorAll('.pessoa-tipo-quantidade');
        if (tipoInputs.length > 0) {
            let sumTipos = 0;
            tipoInputs.forEach(i => sumTipos += parseInt(i.value) || 0);
            const totalInput = tr.querySelector('.pessoa-total');
            if (totalInput) totalInput.value = sumTipos;
        } else {
            const specRows = tr.querySelectorAll('.pessoal-especialidade-row');
            let sum = 0;
            specRows.forEach(r => sum += parseInt(r.querySelector('.pessoa-quantidade').value) || 0);
            const totalInput = tr.querySelector('.pessoa-total');
            if (totalInput) totalInput.value = sum;
        }
    } catch (err) {
        console.error('Erro recalcPostTotals:', err);
    }
}

function initPessoalMatrix() {
    // Colocar listeners nos inputs totais (read-only now)
    // Atualizar totais iniciais
    document.querySelectorAll('tr[data-posto]').forEach(tr => {
        const posto = tr.dataset.posto;
        recalcPostTotals(posto);
    });

    // Listeners para quantidades por tipo (carreira/temporario)
    document.querySelectorAll('.pessoa-tipo-quantidade').forEach(input => {
        input.addEventListener('input', (e) => {
            const posto = input.dataset.posto;
            // quando usuario modifica manualmente tipo, apenas recalcula total
            recalcPostTotals(posto);
            validatePessoalRow(posto);
        });
    });



    // Listeners para quantidades em especialidades
    document.querySelectorAll('.pessoa-quantidade').forEach(input => {
        input.addEventListener('input', (e) => {
            const row = input.closest('.pessoal-especialidade-row');
            if (!row) return;
            const posto = row.dataset.posto || row.closest('tr')?.dataset.posto;
            const tipo = row.dataset.tipo || null;
            if (tipo) {
                updateTipoFromSpecialities(posto, tipo);
            } else {
                recalcPostTotals(posto);
            }
            validatePessoalRow(posto);
        });
    });
}

function addEspecialidade(posto, tipo) {
    try {
        // Só permitir especialidades para os postos com especialidade
        const allowed = ['primeiro_tenente','segundo_tenente','subtenente','primeiro_sargento','segundo_sargento','terceiro_sargento','cabo','soldado','coronel','tenente_coronel','major','capitao'];
        if (!allowed.includes(posto)) {
            if (typeof showAlert === 'function') showAlert('Especialidade não aplicável para este posto', 'error');
            return;
        }

        const container = document.getElementById(`pessoalGroup_${posto}_${tipo}`) || document.getElementById(`pessoalSubdiv_${posto}`);
        if (!container) return;
        const template = document.getElementById('pessoalEspecialidadeTemplate');
        const clone = template.content.cloneNode(true);
        const row = clone.querySelector('.pessoal-especialidade-row');
        row.dataset.posto = posto;
        if (tipo) row.dataset.tipo = tipo;

        const qtyInput = row.querySelector('.pessoa-quantidade');
        qtyInput.addEventListener('input', () => {
            const tipo = row.dataset.tipo || null;
            if (tipo) updateTipoFromSpecialities(posto, tipo);
            else recalcPostTotals(posto);
            validatePessoalRow(posto);
        });

        const removeBtn = row.querySelector('button');
        removeBtn.addEventListener('click', function() { removeEspecialidade(this); });

        container.appendChild(clone);

        // Manter o seletor Arma/Quadro dentro de cada especialidade (por linha). Não remover o seletor ao clonar.

        validatePessoalRow(posto);
    } catch (error) {
        console.error('Erro ao adicionar especialidade:', error);
    }
}  

function removeEspecialidade(button) {
    try {
        const row = button.closest('.pessoal-especialidade-row');
        if (!row) return;
        const posto = row.dataset.posto;
        const tipo = row.dataset.tipo || null;
        row.remove();
        if (tipo) updateTipoFromSpecialities(posto, tipo);
        else recalcPostTotals(posto);
        validatePessoalRow(posto);
    } catch (error) {
        console.error('Erro ao remover especialidade:', error);
    }
}

function validatePessoalRow(posto) {
    try {
        const tr = document.querySelector(`tr[data-posto="${posto}"]`);
        if (!tr) return true;
        const totalInput = tr.querySelector('.pessoa-total');
        const total = parseInt(totalInput.value) || 0;
        const err = tr.querySelector('.pessoa-erro');

        // Se existem inputs de tipo (carreira/temporario), somar e validar por tipo
        const tipoQuantInputs = tr.querySelectorAll('.pessoa-tipo-quantidade');
        if (tipoQuantInputs.length > 0) {
            let sumTipos = 0;
            for (const i of tipoQuantInputs) {
                sumTipos += parseInt(i.value) || 0;
            }
            if (sumTipos !== total) {
                // Autoalinha total com a soma dos tipos para evitar bloqueio
                totalInput.value = sumTipos;
                total = sumTipos;
            }

            // Para cada tipo validar suas especialidades (se houver)
            for (const i of tipoQuantInputs) {
                const tipo = i.dataset.tipo;
                const q = parseInt(i.value) || 0;
                const container = document.getElementById(`pessoalGroup_${posto}_${tipo}`);
                const rows = container ? container.querySelectorAll('.pessoal-especialidade-row') : [];
                if (rows.length === 0) {
                    if (q > 0) {
                        if (err) { err.style.display = 'block'; err.textContent = `Adicione uma especialidade e selecione Arma/Quadro para ${tipo} em ${tr.dataset.postoDisplay}`; }
                        return false;
                    }
                } else {
                    let sum = 0;
                    let missingArma = false;
                    for (const r of rows) {
                        const quantidade = parseInt(r.querySelector('.pessoa-quantidade').value) || 0;
                        sum += quantidade;
                        if (quantidade > 0) {
                            const armaEl = r.querySelector('.pessoa-arma');
                            const armaVal = armaEl ? armaEl.value : '';
                            if (!armaVal) { missingArma = true; break; }
                        }
                    }
                    if (missingArma) {
                        if (err) { err.style.display = 'block'; err.textContent = `Selecione Arma/Quadro nas especialidades de ${tipo} em ${tr.dataset.postoDisplay}`; }
                        return false;
                    }
                    if (sum !== q) {
                        // Autoalinha o total do tipo à soma das especialidades
                        i.value = sum;
                    }
                }
            }
            if (err) err.style.display = 'none';
            return true;
        }

        // fallback: validar como antes (todas as especialidades em um container)
        let sum = 0;
        const rows = tr.querySelectorAll('.pessoal-especialidade-row');
        rows.forEach(r => sum += parseInt(r.querySelector('.pessoa-quantidade').value) || 0);
        if (rows.length === 0) {
            if (total > 0) {
                if (err) { err.style.display = 'block'; err.textContent = 'Adicione uma especialidade e selecione Arma/Quadro para este posto'; }
                return false;
            }
            if (err) err.style.display = 'none';
            return true;
        }
        if (sum !== total) {
            // Autoalinha total ao somatório das especialidades
            totalInput.value = sum;
            if (err) err.style.display = 'none';
            return true;
        }
        if (err) err.style.display = 'none';
        return true;
    } catch (error) {
        console.error('Erro na validação da linha de pessoal:', error);
        return false;
    }
} 

function serializePessoalMatrix(form) {
    try {
        // Validar todas as linhas
        const trs = document.querySelectorAll('tr[data-posto]');
        let entries = [];
        for (const tr of trs) {
            const posto = tr.dataset.posto;
            const postoDisplay = tr.dataset.postoDisplay || tr.querySelector('td').textContent.trim();
            const total = parseInt(tr.querySelector('.pessoa-total').value) || 0;

            // Se o posto tem inputs tipo (carreira/temporario)
            const tipoInputs = tr.querySelectorAll('.pessoa-tipo-quantidade');
            if (tipoInputs.length > 0) {
                let sumTipos = 0;
                for (const ti of tipoInputs) {
                    const tipo = ti.dataset.tipo;
                    const qTipo = parseInt(ti.value) || 0;
                    sumTipos += qTipo;

                    const container = document.getElementById(`pessoalGroup_${posto}_${tipo}`);
                    const specRows = container ? container.querySelectorAll('.pessoal-especialidade-row') : [];
                    if (specRows.length > 0) {
                        let sum = 0;
                        for (const r of specRows) {
                            const armaEl = r.querySelector('.pessoa-arma');
                            const arma = armaEl ? armaEl.value : '';
                            const espec = r.querySelector('.pessoa-especialidade').value || '';
                            const quantidade = parseInt(r.querySelector('.pessoa-quantidade').value) || 0;
                            sum += quantidade;
                            if (quantidade > 0) {
                                entries.push({ posto: postoDisplay, arma: arma, especialidade: espec, tipo: tipo, quantidade: quantidade });
                            }
                        }
                        // Se soma não bate, ainda assim seguimos com as quantidades informadas
                        if (sum !== qTipo) {
                            console.warn(`Pessoal: soma (${sum}) diferente do total tipo (${qTipo}) para ${postoDisplay}/${tipo}; usando somatório informado.`);
                        }
                    } else {
                        // Fallback: permitir salvar apenas com o total por tipo, mesmo sem especialidade
                        if (qTipo > 0) {
                            entries.push({ posto: postoDisplay, arma: '', especialidade: '', tipo: tipo, quantidade: qTipo });
                            console.warn(`Pessoal: fallback sem especialidade para ${postoDisplay}/${tipo}, quantidade=${qTipo}`);
                        }
                    }
                }
                // Se somatório por tipo não bate com total, seguimos assim mesmo
                if (sumTipos !== total) {
                    console.warn(`Pessoal: soma tipos (${sumTipos}) diferente do total (${total}) para ${postoDisplay}; usando somatórios.`);
                }
            } else {
                // Sem tipos: verificar agrupamento geral
                const container = document.getElementById(`pessoalSubdiv_${posto}`);
                const specRows = container ? container.querySelectorAll('.pessoal-especialidade-row') : [];
                if (specRows.length > 0) {
                    let sum = 0;
                    for (const r of specRows) {
                        const quantidade = parseInt(r.querySelector('.pessoa-quantidade').value) || 0;
                        sum += quantidade;
                    }
                    if (sum !== total) {
                        console.warn(`Pessoal: soma especialidades (${sum}) diferente do total (${total}) para ${postoDisplay}; usando somatório.`);
                    }

                    // Registrar entradas com especialidade (arma opcional)
                    for (const r of specRows) {
                        const armaEl = r.querySelector('.pessoa-arma');
                        const armaVal = armaEl ? armaEl.value : '';
                        const especVal = r.querySelector('.pessoa-especialidade').value || '';
                        const qtdVal = parseInt(r.querySelector('.pessoa-quantidade').value) || 0;
                        if (qtdVal > 0) {
                            entries.push({ posto: postoDisplay, arma: armaVal, especialidade: especVal, tipo: '', quantidade: qtdVal });
                        }
                    }
                } else {
                    // Fallback: sem especialidade, usar total diretamente
                    if (total > 0) {
                        entries.push({ posto: postoDisplay, arma: '', especialidade: '', tipo: '', quantidade: total });
                        console.warn(`Pessoal: fallback sem especialidade para ${postoDisplay}, quantidade=${total}`);
                    }
                }
            }
        }

        // Remover anteriores inputs gerados
        const prev = form.querySelectorAll('input[data-generated="pessoal"]');
        prev.forEach(p => p.remove());

        // Flag para backend saber que houve payload de pessoal (quantidade de entradas)
        const marker = document.createElement('input');
        marker.type = 'hidden';
        marker.name = 'pessoal_payload';
        marker.value = String(entries.length);
        marker.dataset.generated = 'pessoal';
        form.appendChild(marker);

        // Atualizar count
        const countInput = form.querySelector('#pessoal_count');
        if (countInput) {
            countInput.value = entries.length;
            countInput.dataset.generated = 'pessoal';
        } else {
            const hid = document.createElement('input'); hid.type = 'hidden'; hid.id = 'pessoal_count'; hid.name = 'pessoal_count'; hid.value = entries.length; hid.dataset.generated = 'pessoal'; form.appendChild(hid);
        }

        // Log para depuração no browser

        // Criar inputs para cada entrada
        entries.forEach((e, idx) => {
            const fields = {
                [`pessoal_posto_${idx}`]: e.posto,
                [`pessoal_arma_${idx}`]: e.arma,
                [`pessoal_especialidade_${idx}`]: e.especialidade,
                [`pessoal_funcao_${idx}`]: '',
                [`pessoal_tipo_${idx}`]: e.tipo || '',
                [`pessoal_quantidade_${idx}`]: e.quantidade,
                [`pessoal_observacoes_${idx}`]: ''
            };
            Object.entries(fields).forEach(([name, value]) => {
                const inp = document.createElement('input'); inp.type = 'hidden'; inp.name = name; inp.value = value; inp.dataset.generated = 'pessoal'; form.appendChild(inp);
            });
        });

        return true;
    } catch (error) {
        console.error('Erro ao serializar matriz de pessoal:', error);
        return false;
    }
}

// Adicionar sistema de segurança
function addSistemaSeguranca(instalacaoIndex) {
    const container = document.getElementById(`sistemasContainer${instalacaoIndex}`);
    if (!container) return;
    
    const template = document.getElementById('empilhadeiraTemplate');
    const clone = template.content.cloneNode(true);
    
    const subIndex = sistemaCounts[instalacaoIndex] || 0;
    
    // Modificar para sistema de segurança
    const subItem = clone.querySelector('.sub-item');
    let html = subItem.innerHTML;
    
    html = html
        .replace(/empilhadeira_tipo/g, 'sistema_seguranca_tipo')
        .replace(/empilhadeira_capacidade/g, 'sistema_descricao')
        .replace(/Capacidade \(kg\)/g, 'Descrição')
        .replace(/type="number"/g, 'type="text"')
        .replace(/step="0\.01"/g, '')
        .replace(/min="0"/g, '')
        .replace(/empilhadeira_quantidade/g, '')
        .replace(/<div class="form-group">.*?Quantidade.*?<\/div>/gs, '')
        .replace(/empilhadeira_foto/g, 'sistema_foto')
        .replace(/empilhadeiraPreview/g, 'sistemaPreview')
        .replace(/{{index}}/g, instalacaoIndex)
        .replace(/{{subIndex}}/g, subIndex);
    
    subItem.innerHTML = html;
    
    container.appendChild(clone);
    sistemaCounts[instalacaoIndex] = subIndex + 1;

    // Atualizar contador oculto correspondente
    const countInput = document.getElementById(`sistemas_count_${instalacaoIndex}`);
    if (countInput) countInput.value = sistemaCounts[instalacaoIndex];
}

// Adicionar equipamento de unitização
function addEquipamentoUnitizacao(instalacaoIndex) {
    const container = document.getElementById(`equipamentosContainer${instalacaoIndex}`);
    if (!container) return;
    
    const template = document.getElementById('empilhadeiraTemplate');
    const clone = template.content.cloneNode(true);
    
    const subIndex = equipamentoCounts[instalacaoIndex] || 0;
    
    // Modificar para equipamento de unitização
    const subItem = clone.querySelector('.sub-item');
    let html = subItem.innerHTML;
    
    html = html
        .replace(/empilhadeira_tipo/g, 'equipamento_unitizacao_tipo')
        .replace(/empilhadeira_capacidade/g, '')
        .replace(/<div class="form-group">.*?Capacidade.*?<\/div>/gs, '')
        .replace(/empilhadeira_quantidade/g, 'equipamento_quantidade')
        .replace(/empilhadeira_foto/g, 'equipamento_foto')
        .replace(/empilhadeiraPreview/g, 'equipamentoPreview')
        .replace(/{{index}}/g, instalacaoIndex)
        .replace(/{{subIndex}}/g, subIndex);
    
    subItem.innerHTML = html;
    
    container.appendChild(clone);
    equipamentoCounts[instalacaoIndex] = subIndex + 1;

    // Atualizar contador oculto correspondente
    const countInput = document.getElementById(`equipamentos_count_${instalacaoIndex}`);
    if (countInput) countInput.value = equipamentoCounts[instalacaoIndex];
}

// Remover sub-item
function removeSubItem(button) {
    const subItem = button.closest('.sub-item');
    if (!subItem) return;

    // Encontrar o container pai (empilhadeiras, sistemas ou equipamentos)
    const container = subItem.closest('[id^="empilhadeirasContainer"], [id^="sistemasContainer"], [id^="equipamentosContainer"]');

    subItem.remove();

    if (container) {
        const match = container.id.match(/(empilhadeirasContainer|sistemasContainer|equipamentosContainer)(\d+)/);
        if (match) {
            const type = match[1];
            const index = parseInt(match[2], 10);
            const newCount = container.querySelectorAll('.sub-item').length;

            if (type === 'empilhadeirasContainer') {
                empilhadeiraCounts[index] = newCount;
                const input = document.getElementById(`empilhadeiras_count_${index}`);
                if (input) input.value = newCount;
            } else if (type === 'sistemasContainer') {
                sistemaCounts[index] = newCount;
                const input = document.getElementById(`sistemas_count_${index}`);
                if (input) input.value = newCount;
            } else if (type === 'equipamentosContainer') {
                equipamentoCounts[index] = newCount;
                const input = document.getElementById(`equipamentos_count_${index}`);
                if (input) input.value = newCount;
            }
        }
    }
}

// Preview de imagem
function previewImage(input, previewId) {
    const preview = document.getElementById(previewId);
    if (!preview) return;
    
    preview.innerHTML = '';
    
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        
        reader.onload = function(e) {
            const img = document.createElement('img');
            img.src = e.target.result;
            preview.appendChild(img);
        }
        
        reader.readAsDataURL(input.files[0]);
    }
}

// Renderizar fotos já existentes (vindas do backend) em um container de preview
function renderExistingPhotos(previewId, fotos) {
    const preview = document.getElementById(previewId);
    if (!preview || !Array.isArray(fotos) || fotos.length === 0) return;
    preview.innerHTML = '';
    fotos.forEach(item => {
        const path = item.caminho_arquivo || item.path || item;
        const id = item.id || item.foto_id || null;
        const url = `/uploads/${path}`;
        const wrapper = document.createElement('div');
        wrapper.className = 'existing-photo';

        if (id !== null) {
            const delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.className = 'btn btn-sm btn-danger mb-1';
            delBtn.textContent = 'Excluir';
            delBtn.addEventListener('click', async () => {
                delBtn.disabled = true;
                try {
                    const res = await fetch(`/foto/${id}/delete`, { method: 'POST' });
                    const data = await res.json();
                    if (data.success) {
                        wrapper.remove();
                    } else {
                        alert(data.message || 'Erro ao excluir foto');
                        delBtn.disabled = false;
                    }
                } catch (err) {
                    alert('Erro ao excluir foto');
                    delBtn.disabled = false;
                }
            });
            wrapper.appendChild(delBtn);
        }

        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = 'Abrir';

        const img = document.createElement('img');
        img.src = url;
        img.alt = 'Foto já enviada';
        img.className = 'info-image';

        wrapper.appendChild(link);
        wrapper.appendChild(img);
        preview.appendChild(wrapper);
    });
}

// Envio do formulário (AJAX apenas quando data-ajax="true" está definido)
const cadastroFormEl = document.getElementById('cadastroForm');
if (cadastroFormEl) {
    cadastroFormEl.addEventListener('submit', async function(e) {
        if (this.dataset.ajax !== 'true') {
            return; // usa submissão padrão do navegador
        }

        e.preventDefault();

        // Executar validação cliente
        if (typeof validarFormulario === 'function' && !validarFormulario()) {
            showAlert('Validação do formulário falhou. Verifique os campos indicados.', 'error');
            return;
        }

        // Serializar e gerar inputs de pessoal a partir da matriz
        if (typeof serializePessoalMatrix === 'function' && !serializePessoalMatrix(this)) {
            // Mensagem já exibida pela função
            return;
        }

        const formData = new FormData(this);

        // Marcar instalações ativas
        document.querySelectorAll('.instalacao-card').forEach(() => {
            formData.append('instalacoes', 'on');
        });

        try {
            showAlert('Enviando dados...', 'info');
            const response = await fetch('/cadastro', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                showModal('Sucesso', result.message);
                showAlert('Cadastro realizado com sucesso', 'success');
                setTimeout(() => {
                    window.location.href = '/';
                }, 1500);
            } else {
                showModal('Erro', result.message);
                showAlert(result.message || 'Erro no servidor', 'error');
            }
        } catch (error) {
            showModal('Erro', 'Erro ao processar o cadastro: ' + error.message);
            showAlert('Erro ao enviar: ' + error.message, 'error');
        }
    });
}

// Modal functions
function showModal(title, message) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    document.getElementById('messageModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('messageModal').style.display = 'none';
}

// Botão de exclusão usado em templates (fallback)
async function deleteFotoAjax(id, btn) {
    if (!id) return;
    if (btn) btn.disabled = true;
    try {
        const res = await fetch(`/foto/${id}/delete`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            const wrapper = btn ? btn.closest('.photo-item, .existing-photo') : null;
            if (wrapper) wrapper.remove();
        } else {
            alert(data.message || 'Erro ao excluir foto');
            if (btn) btn.disabled = false;
        }
    } catch (err) {
        alert('Erro ao excluir foto');
        if (btn) btn.disabled = false;
    }
}